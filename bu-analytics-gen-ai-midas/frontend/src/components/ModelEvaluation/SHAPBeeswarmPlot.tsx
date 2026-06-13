/**
 * SHAP Beeswarm Plot Component
 * Enhanced version with better visualization, tooltips, and density overlay
 * Displays distribution of SHAP values for each feature
 */

import React, { useState, useMemo } from 'react';

interface SHAPBeeswarmPlotProps {
  shapData: {
    values: number[];
    feature_values?: number[];
    mean_abs?: number;
  };
  featureName: string;
  height?: number;
  globalPlotMin?: number;
  globalPlotMax?: number;
}

interface Point {
  idx: number;
  shapValue: number;
  featureValue: number;
  x: number;
  y: number;
  color: string;
}

const SHAPBeeswarmPlot: React.FC<SHAPBeeswarmPlotProps> = ({
  shapData,
  featureName,
  height = 50,
  globalPlotMin,
  globalPlotMax
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<Point | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);

  const { values, feature_values = [] } = shapData;

  // Process data with all improvements
  const processedData = useMemo(() => {
    try {
      if (!values || values.length === 0) return null;

      // Backend now samples to max 5K representative samples for storage
      // SVG rendering still limits to 1K points for optimal performance
      const MAX_DISPLAY_POINTS = 1000;
      const totalCount = values.length;
      
      let displayValues = values;
      let displayFeatureValues = feature_values;
      
      if (totalCount > MAX_DISPLAY_POINTS) {
        // Use systematic sampling to get representative subset
        const step = Math.floor(totalCount / MAX_DISPLAY_POINTS);
        displayValues = values.filter((_, i) => i % step === 0).slice(0, MAX_DISPLAY_POINTS);
        displayFeatureValues = feature_values.filter((_, i) => i % step === 0).slice(0, MAX_DISPLAY_POINTS);
      }

      // Calculate ranges - use reduce for large arrays to avoid stack overflow
      const minShap = displayValues.reduce((min, val) => Math.min(min, val), displayValues[0]);
      const maxShap = displayValues.reduce((max, val) => Math.max(max, val), displayValues[0]);
    
    // Use global range if provided, otherwise calculate local range
    let plotMin: number;
    let plotMax: number;
    
    if (globalPlotMin !== undefined && globalPlotMax !== undefined) {
      // Use global range (shared across all features)
      plotMin = globalPlotMin;
      plotMax = globalPlotMax;
    } else {
      // Calculate local range (fallback for standalone usage)
      const maxAbsShap = Math.max(Math.abs(minShap), Math.abs(maxShap));
      const padding = maxAbsShap * 0.1; // 10% padding
      plotMin = -maxAbsShap - padding;
      plotMax = maxAbsShap + padding;
    }
    
    const shapRange = plotMax - plotMin || 1;
    
    // Zero is always at center (50%)
    const zeroPosition = 0.5;
    const zeroInRange = true; // Always true since we center around zero

    // Feature value range for labels
    const allFeatVals = displayFeatureValues.filter(v => typeof v === 'number');
    const featMin = allFeatVals.length > 0 ? allFeatVals.reduce((min, val) => Math.min(min, val), allFeatVals[0]) : 0;
    const featMax = allFeatVals.length > 0 ? allFeatVals.reduce((max, val) => Math.max(max, val), allFeatVals[0]) : 0;

    // Statistics
    const meanShap = displayValues.reduce((a, b) => a + b, 0) / displayValues.length;
    const stdShap = Math.sqrt(
      displayValues.reduce((sum, val) => sum + Math.pow(val - meanShap, 2), 0) / displayValues.length
    );

    // Normalize feature values for color coding (0-1 range)
    const featRange = featMax - featMin || 1;
    const getNormalizedFeatureValue = (idx: number): number => {
      if (displayFeatureValues.length === 0 || idx >= displayFeatureValues.length) {
        return 0.5;
      }
      const featVal = displayFeatureValues[idx];
      return (featVal - featMin) / featRange;
    };

    // Continuous color gradient (blue -> white -> red)
    const getColor = (normalizedFeat: number): string => {
      // Clamp to 0-1
      const t = Math.max(0, Math.min(1, normalizedFeat));
      
      // Blue (low) -> White (middle) -> Red (high)
      if (t < 0.5) {
        // Blue to white
        const ratio = t * 2;
        const r = Math.round(59 + ratio * (255 - 59));
        const g = Math.round(130 + ratio * (255 - 130));
        const b = Math.round(246 + ratio * (255 - 246));
        return `rgb(${r}, ${g}, ${b})`;
      } else {
        // White to red
        const ratio = (t - 0.5) * 2;
        const r = Math.round(255 - ratio * (255 - 239));
        const g = Math.round(255 - ratio * (255 - 68));
        const b = Math.round(255 - ratio * (255 - 68));
        return `rgb(${r}, ${g}, ${b})`;
      }
    };

    // Improved force-directed jitter algorithm
    // Use plotMin/plotMax for positioning so zero is always centered
    const points: Point[] = displayValues.map((shapValue, idx) => {
      const normalizedPos = (shapValue - plotMin) / shapRange;
      const normalizedFeat = getNormalizedFeatureValue(idx);
      const color = getColor(normalizedFeat);
      
      return {
        idx,
        shapValue,
        featureValue: displayFeatureValues[idx] || 0,
        x: normalizedPos,
        y: 0.5, // Will be adjusted by jitter
        color
      };
    });

    // Sort by SHAP value for better distribution
    points.sort((a, b) => a.shapValue - b.shapValue);

    // Apply force-directed jitter to avoid overlaps
    const radius = 0.015; // Dot radius in normalized coordinates
    const minDistance = radius * 2.5; // Minimum distance between dots

    for (let i = 0; i < points.length; i++) {
      const point = points[i];
      let bestY = 0.5;
      let bestScore = Infinity;

      // Try different y positions and find the one with least overlap
      for (let y = 0.1; y <= 0.9; y += 0.05) {
        let overlap = 0;
        for (let j = 0; j < i; j++) {
          const other = points[j];
          const dx = point.x - other.x;
          const dy = y - other.y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance < minDistance) {
            overlap += (minDistance - distance) / minDistance;
          }
        }
        if (overlap < bestScore) {
          bestScore = overlap;
          bestY = y;
        }
      }
      point.y = bestY;
    }

    // Calculate density for overlay
    const densityBins = 50;
    const density: number[] = new Array(densityBins).fill(0);
    points.forEach(point => {
      const bin = Math.floor(point.x * densityBins);
      if (bin >= 0 && bin < densityBins) {
        density[bin]++;
      }
    });
    const maxDensity = Math.max(...density) || 1;
    const normalizedDensity = density.map(d => d / maxDensity);

    return {
      points,
      minShap, // Actual min (for display)
      maxShap, // Actual max (for display)
      plotMin, // Plot range min (for positioning)
      plotMax, // Plot range max (for positioning)
      shapRange,
      zeroPosition,
      zeroInRange,
      featMin,
      featMax,
      meanShap,
      stdShap,
      normalizedDensity,
      displayCount: displayValues.length,
      totalCount: totalCount
    };
    } catch (error) {
      console.error('Error processing SHAP beeswarm data:', error);
      return null;
    }
  }, [values, feature_values, globalPlotMin, globalPlotMax]);

  if (!processedData) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        No data
      </div>
    );
  }

  const {
    points,
    minShap,
    maxShap,
    plotMin,
    plotMax,
    shapRange,
    zeroPosition,
    zeroInRange,
    featMin,
    featMax,
    meanShap,
    stdShap,
    normalizedDensity,
    displayCount,
    totalCount
  } = processedData;

  const handlePointHover = (point: Point, event: React.MouseEvent<SVGCircleElement>) => {
    setHoveredPoint(point);
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltipPosition({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    });
  };

  const handlePointLeave = () => {
    setHoveredPoint(null);
    setTooltipPosition(null);
  };

  // Format number for display
  const formatNumber = (num: number, decimals: number = 3): string => {
    if (Math.abs(num) < 0.001) return '0';
    if (Math.abs(num) >= 1000) return num.toFixed(decimals);
    return num.toFixed(decimals);
  };

  return (
    <div className="flex items-center gap-3 h-14 relative group">
      {/* Feature name with importance indicator */}
      <div className="w-36 text-right flex-shrink-0">
        <div className="text-sm font-medium text-gray-700 dark:text-white">
          {featureName.replace(/_/g, ' ')}
        </div>
        <div className="text-xs text-gray-500 dark:text-white mt-0.5">
          SHAP: {formatNumber(minShap, 3)} to {formatNumber(maxShap, 3)}
        </div>
      </div>

      {/* Main plot area */}
      <div className="flex-1 relative h-full dark:bg-gray-900" style={{ minHeight: `${height}px` }}>
        {/* Background grid */}
        <div className="absolute inset-0 flex items-center">
          <div className="w-full h-px bg-gray-200 dark:bg-gray-700"></div>
        </div>

        {/* Density overlay */}
        <svg width="100%" height="100%" className="absolute inset-0 z-0 opacity-20" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id={`density-gradient-${featureName.replace(/\s+/g, '-')}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`M 0,100 ${normalizedDensity.map((d, i) => 
              `L ${(i / normalizedDensity.length) * 100},${100 - d * 30}`
            ).join(' ')} L 100,100 Z`}
            fill={`url(#density-gradient-${featureName.replace(/\s+/g, '-')})`}
          />
        </svg>

        {/* SHAP value points */}
        <svg width="100%" height="100%" className="relative z-10">
          {points.map((point) => (
            <circle
              key={point.idx}
              cx={`${point.x * 100}%`}
              cy={`${point.y * 100}%`}
              r="4"
              fill={point.color}
              opacity={hoveredPoint?.idx === point.idx ? 1 : 0.7}
              stroke={hoveredPoint?.idx === point.idx ? '#1f2937' : 'none'}
              strokeWidth={hoveredPoint?.idx === point.idx ? 1.5 : 0}
              className="cursor-pointer transition-all"
              onMouseEnter={(e) => handlePointHover(point, e)}
              onMouseLeave={handlePointLeave}
            />
          ))}
        </svg>

        {/* Tooltip */}
        {hoveredPoint && tooltipPosition && (
          <div
            className="absolute z-50 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg pointer-events-none"
            style={{
              left: `${tooltipPosition.x + 10}px`,
              top: `${tooltipPosition.y - 10}px`,
              transform: 'translateY(-100%)'
            }}
          >
            <div className="font-semibold mb-1">Sample #{hoveredPoint.idx + 1}</div>
            <div>SHAP: <span className="font-mono">{formatNumber(hoveredPoint.shapValue)}</span></div>
            <div>Feature: <span className="font-mono">{formatNumber(hoveredPoint.featureValue, 2)}</span></div>
          </div>
        )}

      </div>

      {/* Feature value range labels */}
      <div className="w-28 text-left flex-shrink-0 text-xs text-gray-600 dark:text-white">
        <div className="font-medium text-gray-700 dark:text-white mb-0.5">Feature Range</div>
        <div className="text-gray-600 dark:text-white mb-1.5">
          {formatNumber(featMin, 2)} - {formatNumber(featMax, 2)}
        </div>
        <div className="text-gray-500 dark:text-white text-[11px]">
          {totalCount.toLocaleString()} samples
        </div>
      </div>
    </div>
  );
};

export default SHAPBeeswarmPlot;


