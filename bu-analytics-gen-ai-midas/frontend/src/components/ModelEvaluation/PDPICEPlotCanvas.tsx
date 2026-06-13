/**
 * PDP ICE Plot Component - Canvas Implementation
 * Optimized for large datasets using HTML5 Canvas
 * Can render thousands of ICE lines efficiently
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

interface PDPPoint {
  x: number;
  y: number;
}

interface PDPICEPlotCanvasProps {
  values: PDPPoint[];
  iceLines: number[][];
  featureName: string;
  width?: number;
  height?: number;
  maxIceLines?: number;
}

const PDPICEPlotCanvas: React.FC<PDPICEPlotCanvasProps> = ({
  values,
  iceLines,
  featureName,
  width = 600,
  height = 256,
  maxIceLines = 100
}) => {
  const { isDark } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width, height });

  // Limit ICE lines based on maxIceLines prop (backend provides max 1000)
  const displayIceLines = useMemo(() => {
    return iceLines.slice(0, maxIceLines);
  }, [iceLines, maxIceLines]);

  // Calculate ranges
  const ranges = useMemo(() => {
    if (values.length === 0) {
      return {
        minX: 0,
        maxX: 1,
        minY: 0,
        maxY: 1,
        rangeX: 1,
        rangeY: 1,
        paddedMinY: 0,
        paddedMaxY: 1,
        totalRangeY: 1
      };
    }

    // Calculate PDP Y range
    const allYValues = values.map(v => v.y);
    const minY = allYValues.reduce((min, val) => Math.min(min, val), allYValues[0]);
    const maxY = allYValues.reduce((max, val) => Math.max(max, val), allYValues[0]);

    // Calculate ICE Y range from displayed lines only
    const allIceYValues = displayIceLines.flat().concat(allYValues);
    const iceMinY = allIceYValues.reduce((min, val) => Math.min(min, val), allIceYValues[0] || minY);
    const iceMaxY = allIceYValues.reduce((max, val) => Math.max(max, val), allIceYValues[0] || maxY);
    const iceRangeY = iceMaxY - iceMinY || 0.1;
    const paddedMinY = iceMinY - iceRangeY * 0.05;
    const paddedMaxY = iceMaxY + iceRangeY * 0.05;
    const totalRangeY = paddedMaxY - paddedMinY;

    const minX = values[0].x;
    const maxX = values[values.length - 1].x;
    const rangeX = maxX - minX || 1;

    return {
      minX,
      maxX,
      minY,
      maxY,
      rangeX,
      rangeY: maxY - minY || 0.1,
      paddedMinY,
      paddedMaxY,
      totalRangeY
    };
  }, [values, displayIceLines]);

  // Update canvas size when container resizes
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const newWidth = rect.width > 0 ? rect.width - 72 : width; // Account for padding (56px left + 16px right)
        const newHeight = rect.height > 0 ? rect.height - 72 : height; // Account for padding (16px top + 56px bottom)
        setCanvasSize({ width: newWidth, height: newHeight });
      }
    };

    const timeoutId = setTimeout(updateSize, 0);
    
    window.addEventListener('resize', updateSize);
    
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
    };
  }, [width, height]);

  // Render to canvas
  useEffect(() => {
    if (!canvasRef.current || values.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const actualWidth = canvasSize.width;
    const actualHeight = canvasSize.height;

    if (actualWidth === 0 || actualHeight === 0) return;

    // Set canvas size accounting for device pixel ratio
    canvas.width = actualWidth * dpr;
    canvas.height = actualHeight * dpr;
    ctx.scale(dpr, dpr);

    // Clear canvas with theme background (match dark panel)
    ctx.fillStyle = isDark ? '#1f2937' : '#f9fafb';
    ctx.fillRect(0, 0, actualWidth, actualHeight);

    // Draw grid lines
    ctx.strokeStyle = isDark ? '#374151' : '#e5e7eb';
    ctx.lineWidth = 0.5;

    // Horizontal grid lines
    for (let i = 0; i <= 5; i++) {
      const y = (i / 5) * actualHeight;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(actualWidth, y);
      ctx.stroke();
    }

    // Vertical grid lines
    for (let i = 0; i <= 5; i++) {
      const x = (i / 5) * actualWidth;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, actualHeight);
      ctx.stroke();
    }

    // Draw ICE lines (very light gray, semi-transparent)
    ctx.strokeStyle = isDark ? '#6b7280' : '#d1d5db';
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.6;

    displayIceLines.forEach((iceLine) => {
      if (iceLine.length === 0) return;

      ctx.beginPath();
      for (let i = 0; i < iceLine.length; i++) {
        const x = (i / (iceLine.length - 1 || 1)) * actualWidth;
        const normalizedY = ((ranges.paddedMaxY - iceLine[i]) / ranges.totalRangeY) * actualHeight;
        if (i === 0) {
          ctx.moveTo(x, normalizedY);
        } else {
          ctx.lineTo(x, normalizedY);
        }
      }
      ctx.stroke();
    });

    // Reset alpha for PDP line
    ctx.globalAlpha = 1.0;

    // Draw PDP line (cyan, thicker)
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    ctx.beginPath();
    values.forEach((point, i) => {
      const x = ((point.x - ranges.minX) / ranges.rangeX) * actualWidth;
      const y = ((ranges.paddedMaxY - point.y) / ranges.totalRangeY) * actualHeight;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

  }, [values, displayIceLines, ranges, canvasSize, isDark]);

  return (
    <div 
      ref={containerRef}
      className="relative w-full h-full"
      style={{ minHeight: `${height}px` }}
    >
      <canvas
        ref={canvasRef}
        className="w-full h-full rounded-md"
        style={{ height: `${height}px` }}
      />
    </div>
  );
};

export default PDPICEPlotCanvas;

