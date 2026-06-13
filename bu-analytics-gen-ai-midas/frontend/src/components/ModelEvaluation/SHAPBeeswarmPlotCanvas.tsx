/**
 * SHAP Beeswarm Plot Component - Canvas Implementation
 * Optimized for large datasets using HTML5 Canvas rendering
 * Displays distribution of SHAP values for each feature
 * Backend samples to 5K representative samples for optimal performance
 */

import React, { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

interface SHAPBeeswarmPlotCanvasProps {
  shapData: {
    values: number[];
    feature_values?: number[];  // Transformed feature values (for SHAP calculation reference)
    original_feature_values?: number[];  // Original feature values (for user-friendly display)
    mean_abs?: number;
    original_feature_name?: string;  // Original column name (for display)
  };
  featureName: string;  // Transformed feature name (model expects this)
  height?: number;
  globalPlotMin?: number;
  globalPlotMax?: number;
}

interface Point {
  idx: number;
  shapValue: number;
  featureValue: number | string;  // Can be number or string (for categorical original values)
  x: number;
  y: number;
  color: string;
}

const SHAPBeeswarmPlotCanvas: React.FC<SHAPBeeswarmPlotCanvasProps> = ({
  shapData,
  featureName,
  height = 56,
  globalPlotMin,
  globalPlotMax
}) => {
  const { isDark } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredPoint, setHoveredPoint] = useState<Point | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [hoveredFeatureRange, setHoveredFeatureRange] = useState(false);
  const [featureRangeTooltipPos, setFeatureRangeTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: height });
  const closeTooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { values, feature_values = [], original_feature_values, original_feature_name } = shapData;
  
  // Use original feature values if available (for user-friendly display), otherwise fallback to transformed values
  // Check if original_feature_values exists AND has values (not just empty array)
  const displayFeatureValues = (original_feature_values && original_feature_values.length > 0) 
    ? original_feature_values 
    : (feature_values && feature_values.length > 0 ? feature_values : []);
  const displayFeatureName = original_feature_name || featureName;

  // Process ALL data (no sampling limit for canvas)
  const processedData = useMemo(() => {
    try {
      if (!values || values.length === 0) return null;

      // Display all samples provided by backend (up to 5K after smart sampling)
      // Canvas can efficiently render thousands of points
      const displayValues = values;
      const displayFeatureValuesForPlot = displayFeatureValues;

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

      // Feature value range for labels (use original values if available)
      // First check if we have feature values
      let featMin: number | string = 0;
      let featMax: number | string = 0;
      
      // Debug: Check what we have
      const hasDisplayValues = displayFeatureValuesForPlot && displayFeatureValuesForPlot.length > 0;
      const hasFeatureValues = feature_values && feature_values.length > 0;
      
      // Use displayFeatureValuesForPlot if available, otherwise fallback to feature_values
      const valuesToUse = hasDisplayValues ? displayFeatureValuesForPlot : (hasFeatureValues ? feature_values : []);
      
      if (valuesToUse.length > 0) {
        // Helper function to check if a value can be converted to a number
        const canConvertToNumber = (v: any): boolean => {
          if (v === null || v === undefined || v === '') return false;
          if (typeof v === 'number' && !isNaN(v) && isFinite(v)) return true;
          if (typeof v === 'string') {
            const trimmed = v.trim();
            if (trimmed === '') return false;
            const num = Number(trimmed);
            return !isNaN(num) && isFinite(num);
          }
          return false;
        };

        // Helper function to convert value to number
        const toNumber = (v: any): number | null => {
          if (typeof v === 'number' && !isNaN(v) && isFinite(v)) return v;
          if (typeof v === 'string') {
            const trimmed = v.trim();
            if (trimmed === '') return null;
            const num = Number(trimmed);
            if (!isNaN(num) && isFinite(num)) return num;
          }
          return null;
        };

        // Try to convert all values to numbers
        const numericFeatVals: number[] = [];
        const nonNumericCount = valuesToUse.filter(v => !canConvertToNumber(v)).length;
        const numericRatio = (valuesToUse.length - nonNumericCount) / valuesToUse.length;

        // If at least 80% of values are numeric, treat as numeric feature
        if (numericRatio >= 0.8) {
          // Convert all values that can be converted to numbers
          for (const v of valuesToUse) {
            const num = toNumber(v);
            if (num !== null) {
              numericFeatVals.push(num);
            }
          }

          if (numericFeatVals.length > 0) {
            // Calculate min/max for numeric values
            featMin = numericFeatVals.reduce((min, val) => Math.min(min, val), numericFeatVals[0]);
            featMax = numericFeatVals.reduce((max, val) => Math.max(max, val), numericFeatVals[0]);
          }
        } else {
          // Less than 80% are numeric - treat as categorical
          const uniqueValues = new Set(valuesToUse.filter(v => v != null && v !== ''));
          if (uniqueValues.size > 0) {
            featMin = 'Categorical';
            featMax = `${uniqueValues.size} unique`;
          }
        }
      }

      // Statistics
      const meanShap = displayValues.reduce((a, b) => a + b, 0) / displayValues.length;
      const stdShap = Math.sqrt(
        displayValues.reduce((sum, val) => sum + Math.pow(val - meanShap, 2), 0) / displayValues.length
      );

      // Normalize feature values for color coding (0-1 range)
      // Handle both numeric and string values (for categorical features)
      const featRange = (typeof featMin === 'number' && typeof featMax === 'number') 
        ? (featMax - featMin || 1) 
        : 1;
      const getNormalizedFeatureValue = (idx: number): number => {
        if (!displayFeatureValuesForPlot || displayFeatureValuesForPlot.length === 0 || idx >= displayFeatureValuesForPlot.length) {
          return 0.5;
        }
        const featVal = displayFeatureValuesForPlot[idx];
        // If string (categorical), convert to numeric for color mapping
        if (typeof featVal === 'string') {
          // Use hash-like approach for consistent color mapping
          const hash = featVal.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
          return (hash % 100) / 100;  // Normalize to 0-1
        }
        // Numeric value - only normalize if featMin/featMax are numbers
        if (typeof featMin === 'number' && typeof featMax === 'number') {
          return (featVal - featMin) / featRange;
        }
        return 0.5;  // Fallback
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

      // Optimized jitter algorithm for large datasets
      // For very large datasets, use simpler jitter to avoid O(n²) complexity
      const points: Point[] = displayValues.map((shapValue, idx) => {
        const normalizedPos = (shapValue - plotMin) / shapRange;
        const normalizedFeat = getNormalizedFeatureValue(idx);
        const color = getColor(normalizedFeat);

        // Simple vertical jitter based on position and index
        // This avoids expensive overlap calculations for large datasets
        const jitterY = 0.3 + (Math.sin(idx * 0.1) * 0.2) + ((idx % 7) / 7) * 0.2;

        // Use original feature value if available, otherwise fallback to transformed
        const featureValue = displayFeatureValuesForPlot[idx] !== undefined 
          ? displayFeatureValuesForPlot[idx] 
          : (feature_values[idx] || 0);

        return {
          idx,
          shapValue,
          featureValue: featureValue as number | string,
          x: normalizedPos,
          y: jitterY,
          color
        };
      });

      // Sort by SHAP value for better visual distribution
      points.sort((a, b) => a.shapValue - b.shapValue);

      // For smaller datasets (< 5000), apply more sophisticated jitter
      if (points.length < 5000) {
        const radius = 0.015;
        const minDistance = radius * 2.5;

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
      }

      // Calculate density for overlay (simplified for large datasets)
      const densityBins = 50;
      const density: number[] = new Array(densityBins).fill(0);
      points.forEach(point => {
        const bin = Math.floor(point.x * densityBins);
        if (bin >= 0 && bin < densityBins) {
          density[bin]++;
        }
      });
      const maxDensity = density.reduce((max, d) => Math.max(max, d), 1);
      const normalizedDensity = density.map(d => d / maxDensity);

      // Get unique categorical values if this is a categorical feature
      const isCategorical = typeof featMin === 'string' || typeof featMax === 'string';
      const uniqueCategoricalValues = isCategorical && valuesToUse.length > 0
        ? Array.from(new Set(valuesToUse.filter(v => v != null && v !== '' && typeof v === 'string'))).sort()
        : [];

      return {
        points,
        minShap,
        maxShap,
        plotMin,
        plotMax,
        shapRange,
        featMin,
        featMax,
        meanShap,
        stdShap,
        normalizedDensity,
        totalCount: displayValues.length,
        isCategorical,
        uniqueCategoricalValues
      };
    } catch (error) {
      console.error('Error processing SHAP beeswarm data:', error);
      return null;
    }
  }, [values, feature_values, globalPlotMin, globalPlotMax]);

  // Update canvas size when container resizes
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        // Use actual width or fallback to a reasonable default
        const width = rect.width > 0 ? rect.width : 600;
        setCanvasSize({ width, height: height });
      }
    };

    // Initial size update
    const timeoutId = setTimeout(updateSize, 0);
    
    // Update on resize
    window.addEventListener('resize', updateSize);
    
    // Use ResizeObserver for more accurate size tracking
    let resizeObserver: ResizeObserver | null = null;
    if (containerRef.current && window.ResizeObserver) {
      resizeObserver = new ResizeObserver(updateSize);
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', updateSize);
      if (resizeObserver && containerRef.current) {
        resizeObserver.unobserve(containerRef.current);
      }
      // Cleanup tooltip timeout on unmount
      if (closeTooltipTimeoutRef.current) {
        clearTimeout(closeTooltipTimeoutRef.current);
        closeTooltipTimeoutRef.current = null;
      }
    };
  }, [height]);

  // Render to canvas
  useEffect(() => {
    if (!canvasRef.current || !processedData) return;
    
    // Use container width if canvasSize not set yet
    const width = canvasSize.width > 0 ? canvasSize.width : (containerRef.current?.getBoundingClientRect().width || 600);
    if (width === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const actualHeight = canvasSize.height || height;

    // Set canvas size accounting for device pixel ratio
    canvas.width = width * dpr;
    canvas.height = actualHeight * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas with theme background
    // Match beeswarm panel background (dark:bg-gray-800)
    ctx.fillStyle = isDark ? '#1f2937' : '#ffffff';
    ctx.fillRect(0, 0, width, actualHeight);

    // Draw background grid line (center line)
    ctx.strokeStyle = isDark ? '#374151' : '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, actualHeight / 2);
    ctx.lineTo(width, actualHeight / 2);
    ctx.stroke();

    // Draw density overlay
    if (processedData.normalizedDensity) {
      ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';
      ctx.beginPath();
      ctx.moveTo(0, actualHeight);
      processedData.normalizedDensity.forEach((d, i) => {
        const x = (i / processedData.normalizedDensity.length) * width;
        const y = actualHeight - (d * actualHeight * 0.3);
        ctx.lineTo(x, y);
      });
      ctx.lineTo(width, actualHeight);
      ctx.closePath();
      ctx.fill();
    }

    // Draw zero line at the correct position (where zero falls in the data range)
    // Calculate where zero is in the normalized range: (0 - plotMin) / shapRange
    const zeroNormalizedPos = (0 - processedData.plotMin) / processedData.shapRange;
    const zeroX = zeroNormalizedPos * width;
    ctx.strokeStyle = isDark ? '#ffffff' : '#000000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(zeroX, 0);
    ctx.lineTo(zeroX, actualHeight);
    ctx.stroke();

    // Draw ALL points (Canvas handles this efficiently)
    const pointRadius = 1.5;
    processedData.points.forEach((point) => {
      const x = point.x * width;
      const y = point.y * actualHeight;

      // Parse color
      const colorMatch = point.color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      if (colorMatch) {
        const [, r, g, b] = colorMatch;
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${hoveredPoint?.idx === point.idx ? 1 : 0.7})`;
      } else {
        ctx.fillStyle = point.color;
      }

      ctx.beginPath();
      ctx.arc(x, y, pointRadius, 0, Math.PI * 2);
      ctx.fill();

      // Highlight hovered point
      if (hoveredPoint?.idx === point.idx) {
        ctx.strokeStyle = isDark ? '#ffffff' : '#1f2937';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    });

  }, [processedData, canvasSize, hoveredPoint, height, isDark]);

  // Handle mouse hover for tooltips (optimized with spatial indexing)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !processedData) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / (rect.width / canvasSize.width);
    const y = (e.clientY - rect.top) / (rect.height / canvasSize.height);

    // Find nearest point (optimized: only check points near mouse)
    let nearest: Point | null = null;
    let minDist = Infinity;
    const searchRadius = 10; // pixels

    // For large datasets, use spatial binning to reduce search space
    const normalizedX = x / canvasSize.width;
    const normalizedY = y / canvasSize.height;

    // Only check points within reasonable distance
    processedData.points.forEach(point => {
      const pointX = point.x * canvasSize.width;
      const pointY = point.y * canvasSize.height;
      const dx = pointX - x;
      const dy = pointY - y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < searchRadius && dist < minDist) {
        minDist = dist;
        nearest = point;
      }
    });

    if (nearest) {
      setHoveredPoint(nearest);
      setTooltipPosition({ x: e.clientX, y: e.clientY });
    } else {
      setHoveredPoint(null);
      setTooltipPosition(null);
    }
  }, [processedData, canvasSize]);

  const handleMouseLeave = useCallback(() => {
    setHoveredPoint(null);
    setTooltipPosition(null);
  }, []);

  if (!processedData) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        No data
      </div>
    );
  }

  const {
    minShap,
    maxShap,
    featMin,
    featMax,
    totalCount,
    isCategorical,
    uniqueCategoricalValues
  } = processedData;

  // Format number or string for display
  const formatValue = (val: number | string, decimals: number = 3): string => {
    if (typeof val === 'string') {
      return val;  // Return string as-is for categorical values
    }
    if (Math.abs(val) < 0.001) return '0';
    if (Math.abs(val) >= 1000) return val.toFixed(decimals);
    return val.toFixed(decimals);
  };

  return (
    <div className="flex items-center gap-3 h-14 relative group">
      {/* Feature name with importance indicator */}
      <div className="w-36 text-right flex-shrink-0">
        <div className="text-sm font-medium text-gray-700 dark:text-white">
          {displayFeatureName.replace(/_/g, ' ')}
        </div>
        <div className="text-xs text-gray-500 dark:text-white mt-0.5">
          SHAP: {formatValue(minShap, 3)} to {formatValue(maxShap, 3)}
        </div>
      </div>

      {/* Main plot area with canvas */}
      <div 
        ref={containerRef}
        className="flex-1 relative h-full dark:bg-gray-900" 
        style={{ minHeight: `${height}px` }}
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full cursor-pointer"
          style={{ height: `${height}px` }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        />
      </div>

      {/* Tooltip */}
      {hoveredPoint && tooltipPosition && (
        <div
          className="fixed z-50 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg pointer-events-none"
          style={{
            left: `${tooltipPosition.x + 10}px`,
            top: `${tooltipPosition.y - 10}px`,
            transform: 'translateY(-100%)'
          }}
        >
          <div>SHAP: <span className="font-mono">{formatValue(hoveredPoint.shapValue)}</span></div>
          <div>Feature: <span className="font-mono">{formatValue(hoveredPoint.featureValue, 2)}</span></div>
        </div>
      )}

      {/* Feature value range labels */}
      <div 
        className="w-28 text-left flex-shrink-0 text-xs text-gray-600 dark:text-white relative"
        onMouseEnter={(e) => {
          // Clear any pending close timeout
          if (closeTooltipTimeoutRef.current) {
            clearTimeout(closeTooltipTimeoutRef.current);
            closeTooltipTimeoutRef.current = null;
          }
          
          if (isCategorical && uniqueCategoricalValues.length > 0) {
            setHoveredFeatureRange(true);
            const rect = e.currentTarget.getBoundingClientRect();
            setFeatureRangeTooltipPos({ x: rect.left, y: rect.top });
          }
        }}
        onMouseLeave={() => {
          // Set a timeout to close the tooltip if mouse doesn't enter tooltip within 200ms
          closeTooltipTimeoutRef.current = setTimeout(() => {
            setHoveredFeatureRange(false);
            setFeatureRangeTooltipPos(null);
            closeTooltipTimeoutRef.current = null;
          }, 200);
        }}
      >
        <div className="font-medium text-gray-700 dark:text-white mb-0.5 flex items-center gap-1">
          <span>Feature Range</span>
          {isCategorical && uniqueCategoricalValues.length > 0 && (
            <span 
              className="text-blue-500 dark:text-white cursor-help hover:text-blue-600 transition-colors" 
              title="Hover to see all unique values"
            >
              ℹ️
            </span>
          )}
        </div>
        {isCategorical ? (
          <div className="text-gray-600 dark:text-white mb-0.5 text-[11px] whitespace-nowrap">
            <span className="font-medium text-gray-700 dark:text-white">Categorical</span>
            <span className="text-gray-500 dark:text-white ml-1">({uniqueCategoricalValues.length} unique)</span>
          </div>
        ) : (
          <div className="text-gray-600 dark:text-white mb-0.5 text-[11px]">
            <span className="font-medium text-gray-700 dark:text-white">Numeric</span>
            <span className="text-gray-500 dark:text-white ml-1">{formatValue(featMin, 2)} - {formatValue(featMax, 2)}</span>
          </div>
        )}
        <div className="text-gray-500 dark:text-white text-[11px]">
          {totalCount.toLocaleString()} samples
        </div>
      </div>
      
      {/* Tooltip showing all unique categorical values - positioned outside to allow hover */}
      {hoveredFeatureRange && featureRangeTooltipPos && isCategorical && uniqueCategoricalValues.length > 0 && (
        <div
          className="fixed z-50 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg"
          style={{
            left: `${featureRangeTooltipPos.x + 10}px`,
            top: `${featureRangeTooltipPos.y - 10}px`,
            transform: 'translateY(-100%)',
            maxWidth: '300px'
          }}
          onMouseEnter={() => {
            // Clear any pending close timeout when mouse enters tooltip
            if (closeTooltipTimeoutRef.current) {
              clearTimeout(closeTooltipTimeoutRef.current);
              closeTooltipTimeoutRef.current = null;
            }
            setHoveredFeatureRange(true);
          }}
          onMouseLeave={() => {
            // Close immediately when mouse leaves tooltip
            setHoveredFeatureRange(false);
            setFeatureRangeTooltipPos(null);
            if (closeTooltipTimeoutRef.current) {
              clearTimeout(closeTooltipTimeoutRef.current);
              closeTooltipTimeoutRef.current = null;
            }
          }}
        >
          <div className="font-semibold mb-2">
            Unique Categorical Values for <span className="text-blue-300">{displayFeatureName.replace(/_/g, ' ')}</span> are ({uniqueCategoricalValues.length}):
          </div>
          <div className="max-h-64 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            {uniqueCategoricalValues.map((val, idx) => (
              <div key={idx} className="text-xs font-mono bg-gray-800 px-2 py-1 rounded">
                {val}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SHAPBeeswarmPlotCanvas;


