/**
 * Feature Importance Visualization Component
 */

import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { FeatureImportance } from '../../types/modelEvaluation';

interface FeatureImportanceChartProps {
  features: FeatureImportance[];
  title?: string;
  topN?: number;
}

export const FeatureImportanceChart: React.FC<FeatureImportanceChartProps> = ({
  features,
  title = 'Feature Importance',
  topN = 15
}) => {
  const [selectedMethod, setSelectedMethod] = useState<'gain' | 'permutation' | 'shap' | 'all'>('all');

  if (!features || features.length === 0) {
    return <div className="p-4 text-gray-500">No feature importance data available</div>;
  }

  // Sort and limit to top N features
  const sortedFeatures = [...features]
    .sort((a, b) => a.rank - b.rank)
    .slice(0, topN);

  // Prepare chart data
  const chartData = sortedFeatures.map(f => ({
    name: f.feature_name.length > 20 ? f.feature_name.substring(0, 17) + '...' : f.feature_name,
    fullName: f.feature_name,
    gain: f.gain_importance,
    permutation: f.permutation_importance,
    shap: f.shap_importance,
    rank: f.rank
  }));

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        
        {/* Method selector */}
        <div className="flex gap-2">
          <button
            onClick={() => setSelectedMethod('all')}
            className={`px-3 py-1 text-sm rounded ${
              selectedMethod === 'all' 
                ? 'bg-blue-500 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All Methods
          </button>
          <button
            onClick={() => setSelectedMethod('gain')}
            className={`px-3 py-1 text-sm rounded ${
              selectedMethod === 'gain' 
                ? 'bg-green-500 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Gain
          </button>
          <button
            onClick={() => setSelectedMethod('permutation')}
            className={`px-3 py-1 text-sm rounded ${
              selectedMethod === 'permutation' 
                ? 'bg-purple-500 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Permutation
          </button>
          <button
            onClick={() => setSelectedMethod('shap')}
            className={`px-3 py-1 text-sm rounded ${
              selectedMethod === 'shap' 
                ? 'bg-orange-500 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            SHAP
          </button>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={400}>
        <BarChart 
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis type="number" domain={[0, 1]} />
          <YAxis dataKey="name" type="category" width={90} fontSize={12} />
          <Tooltip 
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-white p-3 shadow-lg rounded border">
                    <p className="font-semibold mb-2">{data.fullName}</p>
                    <p className="text-sm text-gray-600">Rank: #{data.rank}</p>
                    {payload.map((entry, index) => (
                      <p key={index} className="text-sm" style={{ color: entry.color }}>
                        {entry.name}: {(entry.value as number).toFixed(3)}
                      </p>
                    ))}
                  </div>
                );
              }
              return null;
            }}
          />
          <Legend />
          
          {(selectedMethod === 'all' || selectedMethod === 'gain') && (
            <Bar dataKey="gain" fill="#10B981" name="Gain Importance" />
          )}
          {(selectedMethod === 'all' || selectedMethod === 'permutation') && (
            <Bar dataKey="permutation" fill="#8B5CF6" name="Permutation Importance" />
          )}
          {(selectedMethod === 'all' || selectedMethod === 'shap') && (
            <Bar dataKey="shap" fill="#F59E0B" name="SHAP Importance" />
          )}
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
        <div className="p-3 bg-green-50 rounded">
          <div className="font-semibold text-green-700">Gain Importance</div>
          <div className="text-xs text-gray-600 mt-1">
            Based on model's internal feature splitting gains
          </div>
        </div>
        <div className="p-3 bg-purple-50 rounded">
          <div className="font-semibold text-purple-700">Permutation Importance</div>
          <div className="text-xs text-gray-600 mt-1">
            Impact of shuffling feature values on accuracy
          </div>
        </div>
        <div className="p-3 bg-orange-50 rounded">
          <div className="font-semibold text-orange-700">SHAP Importance</div>
          <div className="text-xs text-gray-600 mt-1">
            Average absolute SHAP values across predictions
          </div>
        </div>
      </div>
    </div>
  );
};

export default FeatureImportanceChart;













