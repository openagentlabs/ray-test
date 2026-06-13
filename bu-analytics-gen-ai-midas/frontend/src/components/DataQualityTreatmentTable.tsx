import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { Download, Play, SkipForward, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import * as XLSX from 'xlsx';

/**
 * Column definition for treatment tables
 */
interface ColumnDef {
  key: string;
  label: string;
  type: 'text' | 'number' | 'percentage' | 'decimal' | 'dropdown';
  options?: string[];
}

/**
 * Table data structure from backend
 */
interface TableData {
  title: string;
  columns: ColumnDef[];
  rows: Record<string, any>[];
}

/**
 * Missing values specific structure with separate numeric/categorical tables
 */
interface MissingValuesTableData {
  title: string;
  numeric_table: TableData;
  categorical_table: TableData;
}

/**
 * Props for DataQualityTreatmentTable component
 */
interface DataQualityTreatmentTableProps {
  treatmentType: 'invalid_values' | 'special_values' | 'outliers' | 'missing_values';
  qcMode: 'auto' | 'manual';
  tableData: TableData | MissingValuesTableData | null;
  skipped?: boolean;
  skipReason?: string;
  code?: string;
  specialMessages?: string[];
  onApplyTreatment?: (codeToApply: string) => void;
  onSkipTreatment?: () => void;
  onUserSelectionChange?: (rowIndex: number, key: string, value: string) => void;
  onRegenerateCode?: (args: {
    treatmentType: 'invalid_values' | 'special_values' | 'outliers' | 'missing_values';
    selections: Record<string, string>;
  }) => Promise<{
    payload?: {
      code?: string;
      table_data?: TableData | MissingValuesTableData;
      special_messages?: string[];
      response?: string;
    };
  }>;
  isApplying?: boolean;
  showMissingFlagOption?: boolean;
  onMissingFlagChange?: (addMissingFlag: boolean) => void;
  addMissingFlag?: boolean;
  // Step-by-step QC props
  treatmentStatus?: 'pending' | 'active' | 'applied' | 'skipped';
  stepInfo?: {
    currentStep: number;
    totalSteps: number;
  };
  // Callback to open Updated EDA view
  onViewUpdatedEDA?: () => void;
}

/**
 * Format cell value based on column type
 */
const formatCellValue = (value: any, type: string): string => {
  if (value === null || value === undefined) return '-';
  
  switch (type) {
    case 'number':
      return typeof value === 'number' ? value.toLocaleString() : String(value);
    case 'percentage':
      return typeof value === 'number' ? `${value.toFixed(2)}%` : String(value);
    case 'decimal':
      return typeof value === 'number' ? value.toFixed(4) : String(value);
    default:
      return String(value);
  }
};

/**
 * Get treatment type display name
 */
const getTreatmentDisplayName = (type: string): string => {
  const names: Record<string, string> = {
    invalid_values: 'Invalid Values',
    special_values: 'Special Values',
    outliers: 'Outliers',
    missing_values: 'Missing Values'
  };
  return names[type] || type;
};

/**
 * Render a single data table with scrollable content
 */
const RenderTable: React.FC<{
  tableData: TableData;
  tableKey: 'single' | 'numeric' | 'categorical';
  onSelectionChange?: (
    tableKey: 'single' | 'numeric' | 'categorical',
    rowIndex: number,
    key: string,
    value: string
  ) => void;
  qcMode?: 'auto' | 'manual';
  disableCustomOption?: boolean;
}> = ({ tableData, tableKey, onSelectionChange, qcMode = 'manual', disableCustomOption = false }) => {
  // Filter out dropdown columns (User Selection) in Auto QC mode
  const filteredColumns = qcMode === 'auto' 
    ? tableData.columns.filter(col => col.type !== 'dropdown')
    : tableData.columns;
  if (!tableData?.rows || tableData.rows.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No data available
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg">
      <table className="min-w-full text-xs divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-8">
              #
            </th>
            {filteredColumns.map((col, idx) => (
              <th 
                key={idx} 
                className="px-2 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
          {tableData.rows.map((row, rowIdx) => (
            <tr 
              key={rowIdx} 
              className={`${rowIdx % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-gray-50 dark:bg-gray-800/50'} hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors`}
            >
              <td className="px-2 py-2 text-gray-500 dark:text-gray-400 text-center">
                {rowIdx + 1}
              </td>
              {filteredColumns.map((col, colIdx) => (
                <td key={colIdx} className="px-2 py-2 whitespace-nowrap">
                  {col.type === 'dropdown' && col.options ? (
                    <select
                      value={row[col.key] || (col.options.includes('Accept') ? 'Accept' : col.options[0] || '')}
                      onChange={(e) => onSelectionChange?.(tableKey, rowIdx, col.key, e.target.value)}
                      className="text-xs border border-gray-300 dark:border-gray-600 rounded px-1 py-0.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      {col.options.map((opt, optIdx) => (
                        <option
                          key={optIdx}
                          value={opt}
                          disabled={disableCustomOption && opt === 'Custom'}
                          title={disableCustomOption && opt === 'Custom' ? 'Not supported yet' : undefined}
                        >
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span
                      className={`text-gray-700 dark:text-gray-200 ${col.key === 'variable' ? 'font-medium' : ''} ${col.key === 'mode' ? 'max-w-[150px] truncate inline-block' : ''}`}
                      title={col.key === 'mode' ? formatCellValue(row[col.key], col.type) : undefined}
                    >
                      {formatCellValue(row[col.key], col.type)}
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/**
 * DataQualityTreatmentTable - Renders structured treatment tables for Data QC
 * 
 * Features:
 * - Displays comprehensive statistics tables for each treatment type
 * - Supports dropdowns for user selection
 * - Shows Apply/Skip buttons in Manual QC mode
 * - Download functionality for treatment reports
 * - Separate tables for numeric/categorical in missing values
 */
const DataQualityTreatmentTable: React.FC<DataQualityTreatmentTableProps> = ({
  treatmentType,
  qcMode,
  tableData,
  skipped = false,
  skipReason,
  code,
  specialMessages,
  onApplyTreatment,
  onSkipTreatment,
  onUserSelectionChange,
  onRegenerateCode,
  isApplying = false,
  showMissingFlagOption = false,
  onMissingFlagChange,
  addMissingFlag = false,
  treatmentStatus,
  stepInfo,
  onViewUpdatedEDA
}) => {
  const [showCode, setShowCode] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [effectiveTableData, setEffectiveTableData] = useState<TableData | MissingValuesTableData | null>(tableData);
  const [effectiveCode, setEffectiveCode] = useState<string>(code || '');
  const [effectiveSpecialMessages, setEffectiveSpecialMessages] = useState<string[] | undefined>(specialMessages);

  const disableCustomOption = treatmentType === 'invalid_values' || treatmentType === 'special_values';

  const extractSelections = useCallback((data: TableData | MissingValuesTableData | null): Record<string, string> => {
    const selections: Record<string, string> = {};
    if (!data) return selections;

    const collect = (rows: Record<string, any>[] | undefined) => {
      if (!rows) return;
      rows.forEach((row) => {
        const variable = String(row?.variable || '').trim();
        const selected = String(row?.user_selection || '').trim();
        if (!variable) return;
        selections[variable] = selected || 'Accept';
      });
    };

    if ('numeric_table' in data) {
      collect(data.numeric_table?.rows);
      collect(data.categorical_table?.rows);
    } else {
      collect(data.rows);
    }
    return selections;
  }, []);

  const [baselineSelections, setBaselineSelections] = useState<Record<string, string>>(
    () => extractSelections(tableData)
  );

  const hasLocalChanges = useRef(false);

  useEffect(() => {
    if (hasLocalChanges.current) return;
    setEffectiveTableData(tableData);
    setEffectiveCode(code || '');
    setEffectiveSpecialMessages(specialMessages);
    setBaselineSelections(extractSelections(tableData));
  }, [tableData, code, specialMessages, extractSelections]);

  const currentSelections = useMemo(() => extractSelections(effectiveTableData), [effectiveTableData, extractSelections]);

  const selectionDirty = useMemo(() => {
    const keys = new Set([...Object.keys(baselineSelections), ...Object.keys(currentSelections)]);
    for (const key of keys) {
      if ((baselineSelections[key] || '') !== (currentSelections[key] || '')) return true;
    }
    return false;
  }, [baselineSelections, currentSelections]);

  const handleSelectionChange = useCallback((
    tableKey: 'single' | 'numeric' | 'categorical',
    rowIndex: number,
    key: string,
    value: string
  ) => {
    hasLocalChanges.current = true;
    setEffectiveTableData((prev) => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev)) as TableData | MissingValuesTableData;
      if ('numeric_table' in next) {
        const targetRows = tableKey === 'numeric'
          ? next.numeric_table?.rows
          : tableKey === 'categorical'
            ? next.categorical_table?.rows
            : undefined;
        if (targetRows && targetRows[rowIndex]) {
          targetRows[rowIndex][key] = value;
        }
      } else if (next.rows?.[rowIndex]) {
        next.rows[rowIndex][key] = value;
      }
      return next;
    });

    onUserSelectionChange?.(rowIndex, key, value);
  }, [onUserSelectionChange]);

  const handleRegenerateCode = useCallback(async () => {
    if (!onRegenerateCode || !selectionDirty) return;
    setIsRegenerating(true);
    try {
      const response = await onRegenerateCode({ treatmentType, selections: currentSelections });
      const payload = response?.payload;
      if (payload?.table_data) {
        setEffectiveTableData(payload.table_data);
        setBaselineSelections(extractSelections(payload.table_data));
      } else {
        setBaselineSelections(currentSelections);
      }
      if (typeof payload?.code === 'string') {
        setEffectiveCode(payload.code);
      }
      if (Array.isArray(payload?.special_messages)) {
        setEffectiveSpecialMessages(payload.special_messages);
      }
    } catch (error) {
      console.error('Failed to regenerate QC code:', error);
    } finally {
      setIsRegenerating(false);
    }
  }, [onRegenerateCode, selectionDirty, treatmentType, currentSelections, extractSelections]);

  /**
   * Download table data as Excel
   */
  const handleDownload = useCallback(() => {
    if (!effectiveTableData) return;
    
    setIsDownloading(true);
    try {
      const wb = XLSX.utils.book_new();
      
      // Check if it's a treatment type with separate numeric/categorical tables
      if ((treatmentType === 'missing_values' || treatmentType === 'invalid_values' || treatmentType === 'special_values') && 'numeric_table' in effectiveTableData) {
        const mvData = effectiveTableData as MissingValuesTableData;
        
        // Add numeric sheet
        if (mvData.numeric_table?.rows?.length > 0) {
          const numericWs = XLSX.utils.json_to_sheet(mvData.numeric_table.rows);
          XLSX.utils.book_append_sheet(wb, numericWs, 'Numeric Variables');
        }
        
        // Add categorical sheet
        if (mvData.categorical_table?.rows?.length > 0) {
          const categoricalWs = XLSX.utils.json_to_sheet(mvData.categorical_table.rows);
          XLSX.utils.book_append_sheet(wb, categoricalWs, 'Categorical Variables');
        }
      } else if ('rows' in effectiveTableData) {
        // Single table
        const ws = XLSX.utils.json_to_sheet((effectiveTableData as TableData).rows);
        XLSX.utils.book_append_sheet(wb, ws, getTreatmentDisplayName(treatmentType));
      }
      
      const fileName = `${treatmentType}_treatment_plan_${new Date().toISOString().split('T')[0]}.xlsx`;
      XLSX.writeFile(wb, fileName);
    } catch (error) {
      console.error('Download failed:', error);
    } finally {
      setIsDownloading(false);
    }
  }, [effectiveTableData, treatmentType]);

  // Render skipped state
  if (skipped) {
    return (
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <SkipForward className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          <h4 className="font-semibold text-yellow-800 dark:text-yellow-200">
            {getTreatmentDisplayName(treatmentType)} - Skipped
          </h4>
        </div>
        <p className="text-sm text-yellow-700 dark:text-yellow-300">
          {skipReason || 'This treatment was skipped. No template was provided.'}
        </p>
      </div>
    );
  }

  // Check for treatment types with split tables (numeric/categorical)
  const hasSplitTables = (treatmentType === 'missing_values' || treatmentType === 'invalid_values' || treatmentType === 'special_values') && effectiveTableData && 'numeric_table' in effectiveTableData;

  return (
    <div className={`bg-white dark:bg-gray-900 border rounded-lg overflow-hidden ${
      treatmentStatus === 'applied' ? 'border-green-300 dark:border-green-700' :
      treatmentStatus === 'skipped' ? 'border-yellow-300 dark:border-yellow-700' :
      treatmentStatus === 'active' ? 'border-blue-300 dark:border-blue-700' :
      'border-gray-200 dark:border-gray-700'
    }`}>
      {/* Header with title, status badge, and download button */}
      <div className={`flex items-center justify-between p-4 border-b ${
        treatmentStatus === 'applied' ? 'border-green-200 dark:border-green-700 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20' :
        treatmentStatus === 'skipped' ? 'border-yellow-200 dark:border-yellow-700 bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20' :
        'border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20'
      }`}>
        <div className="flex items-center gap-2">
          <CheckCircle2 className={`h-5 w-5 ${
            treatmentStatus === 'applied' ? 'text-green-600 dark:text-green-400' :
            treatmentStatus === 'skipped' ? 'text-yellow-600 dark:text-yellow-400' :
            'text-blue-600 dark:text-blue-400'
          }`} />
          <h4 className="font-semibold text-gray-900 dark:text-white">
            {effectiveTableData && 'title' in effectiveTableData ? effectiveTableData.title : getTreatmentDisplayName(treatmentType)}
          </h4>
          <span className={`text-xs px-2 py-0.5 rounded-full ${qcMode === 'auto' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'}`}>
            {qcMode === 'auto' ? 'Auto QC' : 'Manual QC'}
          </span>
          {/* Treatment Status Badge */}
          {treatmentStatus === 'applied' && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 font-medium">
              ✅ Treatment Applied
            </span>
          )}
          {treatmentStatus === 'skipped' && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 font-medium">
              ⏭️ Skipped
            </span>
          )}
          {treatmentStatus === 'active' && stepInfo && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-medium">
              Step {stepInfo.currentStep} of {stepInfo.totalSteps}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Missing Flag Radio Option - Only shown in Manual QC for missing_values */}
          {showMissingFlagOption && treatmentType === 'missing_values' && (
            <div className="flex items-center gap-3 px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg">
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Add Missing Flag:</span>
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name="missingFlag"
                  checked={addMissingFlag}
                  onChange={() => onMissingFlagChange?.(true)}
                  className="w-3.5 h-3.5 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <span className="text-xs text-gray-600 dark:text-gray-400">Yes</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name="missingFlag"
                  checked={!addMissingFlag}
                  onChange={() => onMissingFlagChange?.(false)}
                  className="w-3.5 h-3.5 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <span className="text-xs text-gray-600 dark:text-gray-400">No</span>
              </label>
            </div>
          )}
          <button
            onClick={handleDownload}
            disabled={isDownloading || !effectiveTableData}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span>{isDownloading ? 'Downloading...' : 'Download'}</span>
          </button>
        </div>
      </div>

      {/* Special messages */}
      {effectiveSpecialMessages && effectiveSpecialMessages.length > 0 && (
        <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-700">
          {effectiveSpecialMessages.map((msg, idx) => (
            <p key={idx} className="text-xs text-amber-700 dark:text-amber-300">⚠️ {msg}</p>
          ))}
        </div>
      )}

      {/* Table content */}
      <div className="p-4 space-y-4">
        {hasSplitTables ? (
          // Treatment types with separate numeric and categorical tables (missing_values, invalid_values)
          <>
            {/* Numeric Variables Table */}
            {(effectiveTableData as MissingValuesTableData).numeric_table?.rows?.length > 0 && (
              <div className="space-y-2">
                <h5 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  📊 Numeric Variables ({(effectiveTableData as MissingValuesTableData).numeric_table.rows.length})
                </h5>
                <RenderTable 
                  tableData={(effectiveTableData as MissingValuesTableData).numeric_table}
                  tableKey="numeric"
                  onSelectionChange={handleSelectionChange}
                  qcMode={qcMode}
                  disableCustomOption={disableCustomOption}
                />
              </div>
            )}
            
            {/* Categorical Variables Table */}
            {(effectiveTableData as MissingValuesTableData).categorical_table?.rows?.length > 0 && (
              <div className="space-y-2">
                <h5 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  📋 Categorical Variables ({(effectiveTableData as MissingValuesTableData).categorical_table.rows.length})
                </h5>
                <RenderTable 
                  tableData={(effectiveTableData as MissingValuesTableData).categorical_table}
                  tableKey="categorical"
                  onSelectionChange={handleSelectionChange}
                  qcMode={qcMode}
                  disableCustomOption={disableCustomOption}
                />
              </div>
            )}
            
            {/* Show message if both tables are empty */}
            {!(effectiveTableData as MissingValuesTableData).numeric_table?.rows?.length && 
             !(effectiveTableData as MissingValuesTableData).categorical_table?.rows?.length && (
              <div className="text-center text-gray-500 dark:text-gray-400 py-4">
                No variables with issues detected
              </div>
            )}
          </>
        ) : effectiveTableData && 'rows' in effectiveTableData ? (
          // Single table for other treatment types
          <RenderTable 
            tableData={effectiveTableData as TableData}
            tableKey="single"
            onSelectionChange={handleSelectionChange}
            qcMode={qcMode}
            disableCustomOption={disableCustomOption}
          />
        ) : (
          <div className="text-center text-gray-500 dark:text-gray-400 py-4">
            No treatment data available
          </div>
        )}
      </div>

      {/* Code section (collapsible) */}
      {effectiveCode && effectiveCode.trim() !== '# No code to display' && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setShowCode(!showCode)}
            className="w-full flex items-center justify-between p-3 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <span className="flex items-center gap-2">
              <span className="text-green-600 dark:text-green-400">📝</span>
              Generated Code
            </span>
            {showCode ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          
          {showCode && (
            <div className="p-4 pt-0">
              <div className="bg-gray-900 text-green-400 p-3 rounded-lg text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto">
                <pre>{effectiveCode}</pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action buttons (Manual QC only) - Only show for active treatments or if no status tracking */}
      {qcMode === 'manual' && (onApplyTreatment || onSkipTreatment) && (!treatmentStatus || treatmentStatus === 'active') && (
        <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          {onRegenerateCode && (
            <button
              onClick={handleRegenerateCode}
              disabled={!selectionDirty || isApplying || isRegenerating}
              className="flex items-center gap-1 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title={!selectionDirty ? 'Change user selection to enable re-generate' : undefined}
            >
              <Play className="h-4 w-4" />
              <span>{isRegenerating ? 'Regenerating...' : 'Re-generate Code'}</span>
            </button>
          )}
          {onSkipTreatment && (
            <button
              onClick={onSkipTreatment}
              disabled={isApplying}
              className="flex items-center gap-1 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              <SkipForward className="h-4 w-4" />
              <span>Skip This Step</span>
            </button>
          )}
          {onApplyTreatment && (
            <button
              onClick={() => onApplyTreatment(effectiveCode)}
              disabled={isApplying}
              className="flex items-center gap-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isApplying ? (
                <>
                  <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Applying...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span>Apply Treatment</span>
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Applied Treatment Success Message with View Updated EDA button */}
      {treatmentStatus === 'applied' && (
        <div className="p-4 border-t border-green-200 dark:border-green-700 bg-green-50 dark:bg-green-900/20">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-700 dark:text-green-300">
                Treatment applied successfully!
              </span>
            </div>
            {onViewUpdatedEDA && (
              <button
                onClick={onViewUpdatedEDA}
                className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-700 transition-colors"
              >
                <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                View Updated EDA
              </button>
            )}
          </div>
        </div>
      )}

      {/* Skipped Treatment Message */}
      {treatmentStatus === 'skipped' && (
        <div className="p-4 border-t border-yellow-200 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20">
          <div className="flex items-center gap-2">
            <SkipForward className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
            <span className="text-sm font-medium text-yellow-700 dark:text-yellow-300">
              Treatment skipped
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataQualityTreatmentTable;
