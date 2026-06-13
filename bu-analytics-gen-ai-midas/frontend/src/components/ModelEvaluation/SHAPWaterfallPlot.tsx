/**
 * SHAP Waterfall Plot Component
 * Displays single prediction explanation showing feature contributions
 */

import React from 'react';
import { parseNumericValue } from '../../utils/displayMissingValue';

interface WaterfallFeature {
  feature: string;
  feature_value?: number | string | null;
  shap_value?: number | string | null;
}

interface SHAPWaterfallPlotProps {
  waterfallData: WaterfallFeature[];
  baseValue: number;
  modelColor?: string;
}

const SHAPWaterfallPlot: React.FC<SHAPWaterfallPlotProps> = ({
  waterfallData,
  baseValue,
  modelColor = '#3b82f6'
}) => {
  if (!waterfallData || waterfallData.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-white py-8">No waterfall data available</div>
    );
  }

  const safeBaseValue = parseNumericValue(baseValue) ?? baseValue ?? 0;
  const sanitizedFeatures = waterfallData.map((feature) => ({
    ...feature,
    shap_value: parseNumericValue(feature.shap_value) ?? 0
  }));

  try {
    // Calculate cumulative values
    let cumulative = safeBaseValue;
    const featuresWithCumulative = sanitizedFeatures.map((feature) => {
      const prevCumulative = cumulative;
      cumulative += feature.shap_value as number;
      return {
        ...feature,
        prevCumulative,
        cumulative,
        isPositive: (feature.shap_value as number) > 0
      };
    });

    const finalPrediction = cumulative;

    // Calculate the range for the scale
    const allValues = [safeBaseValue, ...featuresWithCumulative.map(f => f.cumulative), finalPrediction];
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);
    
    // Add padding to the range for better visualization
    const padding = (maxVal - minVal) * 0.15; // 15% padding on each side
    const paddedMin = minVal - padding;
    const paddedMax = maxVal + padding;
    const range = paddedMax - paddedMin || 1;

    const normalize = (val: number) => (val - paddedMin) / range;
    
    // Scale labels: show the actual data range (rounded nicely)
    const scaleMin = Math.floor(minVal * 10) / 10; // Round down to 1 decimal
    const scaleMax = Math.ceil(maxVal * 10) / 10;  // Round up to 1 decimal

    return (
      <div className="relative">
        <div className="space-y-1">
          {/* Base Value */}
          <div className="flex items-center gap-3 py-1">
            <div className="w-40 text-right flex-shrink-0">
              <div className="text-xs font-semibold text-gray-700 dark:text-white">Base Value</div>
              <div className="text-xs text-gray-500 dark:text-white">E[f(x)]</div>
            </div>
            <div className="flex-1 relative" style={{ height: '36px' }}>
              {/* Background track */}
              <div className="absolute inset-0 bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded border border-gray-200 dark:border-gray-800"></div>
              {/* Base value bar - from normalized minimum (0%) to baseValue position */}
              <div
                className="absolute top-1 bottom-1 rounded-sm shadow z-20"
                style={{
                  left: '0%',
                  width: `${normalize(safeBaseValue) * 100}%`,
                  backgroundColor: '#64748b'
                }}
              />
              {/* Base value label: always placed at the right end of the base bar */}
              <div
                className="absolute text-xs font-semibold whitespace-nowrap z-30"
                style={{
                  left: `${normalize(safeBaseValue) * 100}%`,
                  top: '50%',
                  // Center vertically on the bar, then nudge slightly to the RIGHT
                  transform: 'translateY(-50%) translateX(6px)'
                }}
              >
                <span className="px-1.5 py-0.5 rounded shadow-sm bg-gray-700 text-white">
                  {safeBaseValue.toFixed(2)}
                </span>
              </div>
            </div>
          </div>

        {/* Feature Contributions */}
        {featuresWithCumulative.map((feature, idx) => {
          const prevPos = normalize(feature.prevCumulative);
          const currPos = normalize(feature.cumulative);
          const isPositive = feature.shap_value > 0;
          
          // Bar starts at previous cumulative and extends to current cumulative
          const barStart = Math.min(prevPos, currPos);
          const barEnd = Math.max(prevPos, currPos);
          const barWidth = (barEnd - barStart) * 100;

          return (
            <div key={idx} className="flex items-center gap-3 py-1">
              <div className="w-40 text-right flex-shrink-0">
                <div className="text-xs font-medium text-gray-700 dark:text-white capitalize truncate">
                  {feature.feature.replace(/_/g, ' ')}
                </div>
                <div className="text-xs text-gray-500 dark:text-white">
                  = {typeof feature.feature_value === 'number' && feature.feature_value < 1
                    ? feature.feature_value.toFixed(2)
                    : typeof feature.feature_value === 'number'
                    ? feature.feature_value.toLocaleString()
                    : String(feature.feature_value)}
                </div>
              </div>
              <div className="flex-1 relative" style={{ height: '36px' }}>
                {/* Background track */}
                <div className="absolute inset-0 bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded border border-gray-200 dark:border-gray-800"></div>
                
                {/* Waterfall bar - extends from previous to current cumulative */}
                <div
                  className="absolute top-1 bottom-1 rounded-sm shadow z-20"
                  style={{
                    left: `${barStart * 100}%`,
                    width: `${barWidth}%`,
                    backgroundColor: isPositive ? '#06b6d4' : '#f43f5e',
                    minWidth: '2px' // Ensure even tiny contributions are visible
                  }}
                />

                {/* Value label placed at the end of the bar (where the bar finishes) */}
                <div
                  className="absolute text-xs font-semibold whitespace-nowrap z-30"
                  style={{
                    // Always anchor label at the visual RIGHT edge of the bar.
                    // For positive SHAP: barStart = prev, barEnd = curr
                    // For negative SHAP: barStart = curr, barEnd = prev
                    // So barEnd is consistently the rightmost end in screen space.
                    left: `${barEnd * 100}%`,
                    top: '50%',
                    // Center vertically on the bar, then nudge slightly to the RIGHT
                    // of the bar end for both positive and negative contributions
                    transform: 'translateY(-50%) translateX(6px)'
                  }}
                >
                  <span
                    className="px-1.5 py-0.5 rounded shadow-sm"
                    style={{
                      backgroundColor: isPositive ? '#06b6d4' : '#f43f5e',
                      color: 'white'
                    }}
                  >
                    {feature.shap_value > 0 ? '+' : ''}{feature.shap_value.toFixed(3)}
                  </span>
                </div>

                {/* End position marker line */}
                <div
                  className="absolute top-0 bottom-0 w-px bg-gray-400 z-10"
                  style={{
                    left: `${currPos * 100}%`
                  }}
                ></div>
              </div>
            </div>
          );
        })}

        {/* Final Prediction */}
        <div className="flex items-center gap-3 py-1 mt-3 pt-3 border-t-2 border-gray-400 dark:border-gray-700">
          <div className="w-40 text-right flex-shrink-0">
            <div className="text-xs font-bold text-gray-800 dark:text-white">f(x)</div>
            <div className="text-xs text-gray-600 dark:text-white">Final Prediction</div>
          </div>
          <div className="flex-1 relative" style={{ height: '36px' }}>
            {/* Background track */}
            <div className="absolute inset-0 bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded border-2 border-gray-400 dark:border-gray-700"></div>
            {/* Final prediction bar - from normalized minimum (0%) to finalPrediction position */}
            <div
              className="absolute top-1 bottom-1 rounded-sm shadow z-20"
              style={{
                left: '0%',
                width: `${normalize(finalPrediction) * 100}%`,
                backgroundColor: modelColor
              }}
            />
            {/* Final prediction label: always placed at the right end of the bar */}
            <div
              className="absolute text-xs font-bold whitespace-nowrap z-30"
              style={{
                left: `${normalize(finalPrediction) * 100}%`,
                top: '50%',
                // Center vertically on the bar, then nudge slightly to the RIGHT
                transform: 'translateY(-50%) translateX(6px)'
              }}
            >
              <span
                className="px-2 py-0.5 rounded-sm shadow-sm text-white"
                style={{ backgroundColor: modelColor }}
              >
                {finalPrediction.toFixed(3)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Scale */}
      <div className="mt-6 px-40">
        <div className="flex justify-between text-xs text-gray-600 dark:text-white mb-1">
          <span>{scaleMin.toFixed(1)}</span>
          <span className="font-semibold text-gray-800 dark:text-white">Prediction Score</span>
          <span>{scaleMax.toFixed(1)}</span>
        </div>
        <div className="h-px bg-gray-400 dark:bg-gray-700"></div>
      </div>
    </div>
  );
  } catch (error) {
    console.error('SHAPWaterfallPlot render error', error);
    return (
      <div className="text-center text-red-600 py-8">
        Unable to render explainability waterfall data.
      </div>
    );
  }
};

export default SHAPWaterfallPlot;


