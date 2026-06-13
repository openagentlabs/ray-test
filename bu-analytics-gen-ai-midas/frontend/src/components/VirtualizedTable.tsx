import React, { useMemo, useState, useEffect } from 'react';

// Dynamic import with fallback
let FixedSizeList: any = null;
let reactWindowLoaded = false;

// Try to load react-window dynamically
const loadReactWindow = async () => {
  if (reactWindowLoaded) return;
  try {
    const module = await import('react-window');
    FixedSizeList = module.FixedSizeList;
    reactWindowLoaded = true;
  } catch (e) {
    console.warn('react-window failed to load, using fallback table', e);
  }
};

interface TableColumn {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  render?: (value: any, row: any) => React.ReactNode;
}

interface VirtualizedTableProps {
  columns: TableColumn[];
  data: any[];
  height?: number;
  rowHeight?: number;
  className?: string;
}

/**
 * VirtualizedTable component for rendering large tables efficiently
 * Only renders visible rows
 */
const VirtualizedTable: React.FC<VirtualizedTableProps> = ({
  columns,
  data,
  height = 400,
  rowHeight = 50,
  className = '',
}) => {
  const [useVirtualization, setUseVirtualization] = useState(false);

  useEffect(() => {
    loadReactWindow().then(() => {
      if (FixedSizeList) {
        setUseVirtualization(true);
      }
    });
  }, []);

  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const row = data[index] as Record<string, any>;
    const isEven = index % 2 === 0;

    return (
      <div
        style={style}
        className={`flex border-b border-gray-200 ${isEven ? 'bg-white' : 'bg-gray-50'}`}
      >
        {columns.map((column, colIndex) => {
          const value = row[column.key];
          const content = column.render ? column.render(value, row as any) : value;
          const alignClass = column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left';

          return (
            <div
              key={column.key}
              className={`px-4 py-2 text-gray-900 ${alignClass} flex-1`}
              style={{ minWidth: `${100 / columns.length}%` }}
            >
              {content}
            </div>
          );
        })}
      </div>
    );
  };

  if (data.length === 0) {
    return (
      <div className={`border border-gray-300 rounded-lg ${className}`}>
        <p className="text-center py-8 text-gray-500">No data available</p>
      </div>
    );
  }

  // Fallback to regular table if react-window is not available
  if (!useVirtualization || !FixedSizeList) {
    return (
      <div className={`border border-gray-300 rounded-lg overflow-auto ${className}`} style={{ maxHeight: height }}>
        {/* Table Header */}
        <div className="flex bg-gray-100 border-b border-gray-300 sticky top-0 z-10">
          {columns.map((column) => {
            const alignClass = column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left';
            return (
              <div
                key={column.key}
                className={`px-4 py-2 font-semibold text-gray-700 ${alignClass} flex-1`}
                style={{ minWidth: `${100 / columns.length}%` }}
              >
                {column.label}
              </div>
            );
          })}
        </div>

        {/* Regular Rows (fallback) */}
        {data.map((row: any, index: number) => {
          const isEven = index % 2 === 0;
          return (
            <div
              key={index}
              className={`flex border-b border-gray-200 ${isEven ? 'bg-white' : 'bg-gray-50'}`}
            >
              {columns.map((column) => {
                const value = (row as Record<string, any>)[column.key];
                const content = column.render ? column.render(value, row as any) : value;
                const alignClass = column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left';
                return (
                  <div
                    key={column.key}
                    className={`px-4 py-2 text-gray-900 ${alignClass} flex-1`}
                    style={{ minWidth: `${100 / columns.length}%` }}
                  >
                    {content}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`border border-gray-300 rounded-lg overflow-hidden ${className}`}>
      {/* Table Header */}
      <div className="flex bg-gray-100 border-b border-gray-300 sticky top-0 z-10">
        {columns.map((column) => {
          const alignClass = column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left';
          return (
            <div
              key={column.key}
              className={`px-4 py-2 font-semibold text-gray-700 ${alignClass} flex-1`}
              style={{ minWidth: `${100 / columns.length}%` }}
            >
              {column.label}
            </div>
          );
        })}
      </div>

      {/* Virtualized Rows */}
      <FixedSizeList
        height={height}
        itemCount={data.length}
        itemSize={rowHeight}
        width="100%"
      >
        {Row}
      </FixedSizeList>
    </div>
  );
};

export default VirtualizedTable;

