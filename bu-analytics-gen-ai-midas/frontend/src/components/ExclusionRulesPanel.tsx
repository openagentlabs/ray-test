import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Plus, X, ChevronDown, AlertTriangle, AlertCircle } from 'lucide-react';
import { fastApiService } from '../services/fastApiService';
import {
  ExclusionCondition,
  ExclusionGroup,
  ExclusionColumnType,
  WaterfallRow,
  ExclusionWarning,
} from './steps/types';

interface ColumnInfo {
  name: string;
  type: string;
  logical_type?: string;
  is_date?: boolean;
  unique_count: number;
  sample_values?: Record<string, number>;
  numerical_stats?: {
    min: number | null;
    max: number | null;
    mean: number | null;
  };
}

interface ExclusionRulesPanelProps {
  datasetAnalysis: {
    columns: ColumnInfo[];
    totalRows: number;
  } | null;
  selectedDataSources: any[];
  targetVariable: string;
  onExclusionRulesChange?: (groups: ExclusionGroup[]) => void;
  onFilteredRowsChange?: (filteredRows: number) => void;
  originalRowCount?: number | null;
}

const OPERATORS_BY_TYPE: Record<ExclusionColumnType, { value: string; label: string }[]> = {
  Numeric: [
    { value: '=', label: '=' },
    { value: '!=', label: '!=' },
    { value: '>', label: '>' },
    { value: '>=', label: '>=' },
    { value: '<', label: '<' },
    { value: '<=', label: '<=' },
    { value: 'BETWEEN', label: 'BETWEEN' },
    { value: 'NOT BETWEEN', label: 'NOT BETWEEN' },
    { value: 'IS NULL', label: 'IS NULL' },
    { value: 'IS NOT NULL', label: 'IS NOT NULL' },
  ],
  Categorical: [
    { value: '=', label: '=' },
    { value: '!=', label: '!=' },
    { value: 'IN', label: 'IN' },
    { value: 'NOT IN', label: 'NOT IN' },
    { value: 'STARTS WITH', label: 'STARTS WITH' },
    { value: 'CONTAINS', label: 'CONTAINS' },
    { value: 'IS NULL', label: 'IS NULL' },
    { value: 'IS NOT NULL', label: 'IS NOT NULL' },
  ],
  Date: [
    { value: '=', label: '=' },
    { value: '!=', label: '!=' },
    { value: '>', label: 'after' },
    { value: '>=', label: 'on/after' },
    { value: '<', label: 'before' },
    { value: '<=', label: 'on/before' },
    { value: 'BETWEEN', label: 'BETWEEN' },
    { value: 'NOT BETWEEN', label: 'NOT BETWEEN' },
    { value: 'IS NULL', label: 'IS NULL' },
    { value: 'IS NOT NULL', label: 'IS NOT NULL' },
  ],
  Boolean: [
    { value: '= TRUE', label: '= TRUE' },
    { value: '= FALSE', label: '= FALSE' },
    { value: 'IS NULL', label: 'IS NULL' },
    { value: 'IS NOT NULL', label: 'IS NOT NULL' },
  ],
};

function getColumnType(col: ColumnInfo): ExclusionColumnType {
  if (col.logical_type === 'Date' || col.is_date) return 'Date';
  if (col.type === 'Numerical') return 'Numeric';
  if (col.unique_count === 2) {
    const vals = col.sample_values ? Object.keys(col.sample_values) : [];
    const boolLike = vals.every(v => 
      ['true', 'false', '0', '1', 'yes', 'no'].includes(v.toLowerCase())
    );
    if (boolLike) return 'Boolean';
  }
  return 'Categorical';
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 11);
}

function createEmptyCondition(columns: ColumnInfo[]): ExclusionCondition {
  const firstCol = columns[0];
  const colType = firstCol ? getColumnType(firstCol) : 'Categorical';
  return {
    id: generateId(),
    column: firstCol?.name || '',
    columnType: colType,
    operator: OPERATORS_BY_TYPE[colType][0]?.value || '=',
    value: null,
    connector: 'AND',
  };
}

function createEmptyGroup(columns: ColumnInfo[]): ExclusionGroup {
  return {
    id: generateId(),
    conditions: [createEmptyCondition(columns)],
  };
}

function conditionToText(cond: ExclusionCondition): string {
  const { column, operator, value } = cond;
  if (operator === 'IS NULL' || operator === 'IS NOT NULL') {
    return `${column} ${operator}`;
  }
  if (operator === 'IN' || operator === 'NOT IN') {
    const vals = Array.isArray(value) ? value.join(', ') : value;
    return `${column} ${operator} (${vals})`;
  }
  if (operator === 'BETWEEN' || operator === 'NOT BETWEEN') {
    const [min, max] = Array.isArray(value) ? value : [value, value];
    return `${column} ${operator} ${min} AND ${max}`;
  }
  return `${column} ${operator} ${value}`;
}

function groupToNaturalLanguage(group: ExclusionGroup): string {
  return group.conditions
    .map((c, i) => {
      const text = conditionToText(c);
      if (i === 0) return text;
      return `${group.conditions[i - 1].connector} ${text}`;
    })
    .join(' ');
}

const ExclusionRulesPanel: React.FC<ExclusionRulesPanelProps> = ({
  datasetAnalysis,
  selectedDataSources,
  targetVariable,
  onExclusionRulesChange,
  onFilteredRowsChange,
  originalRowCount,
}) => {
  const [groups, setGroups] = useState<ExclusionGroup[]>([]);
  const [waterfall, setWaterfall] = useState<WaterfallRow[]>([]);
  const [warnings, setWarnings] = useState<ExclusionWarning[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [openColumnDropdown, setOpenColumnDropdown] = useState<string | null>(null);
  const [openOperatorDropdown, setOpenOperatorDropdown] = useState<string | null>(null);
  const [openConnectorDropdown, setOpenConnectorDropdown] = useState<string | null>(null);
  const [columnSearchQuery, setColumnSearchQuery] = useState<string>('');

  // Refs for dropdowns to handle click outside
  const columnDropdownRef = useRef<HTMLDivElement>(null);
  const operatorDropdownRef = useRef<HTMLDivElement>(null);
  const connectorDropdownRef = useRef<HTMLDivElement>(null);

  const columns = useMemo(() => datasetAnalysis?.columns || [], [datasetAnalysis]);

  // Filter columns based on search query
  const filteredColumns = useMemo(() => {
    if (!columnSearchQuery.trim()) return columns;
    const query = columnSearchQuery.toLowerCase();
    return columns.filter(col => 
      col.name.toLowerCase().includes(query) ||
      getColumnType(col).toLowerCase().includes(query)
    );
  }, [columns, columnSearchQuery]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Close column dropdown
      if (columnDropdownRef.current && !columnDropdownRef.current.contains(event.target as Node)) {
        setOpenColumnDropdown(null);
        setColumnSearchQuery('');
      }
      // Close operator dropdown
      if (operatorDropdownRef.current && !operatorDropdownRef.current.contains(event.target as Node)) {
        setOpenOperatorDropdown(null);
      }
      // Close connector dropdown
      if (connectorDropdownRef.current && !connectorDropdownRef.current.contains(event.target as Node)) {
        setOpenConnectorDropdown(null);
      }
    };

    if (openColumnDropdown || openOperatorDropdown || openConnectorDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openColumnDropdown, openOperatorDropdown, openConnectorDropdown]);

  const getTopValues = useCallback((columnName: string): string[] => {
    const col = columns.find(c => c.name === columnName);
    if (!col?.sample_values) return [];
    return Object.entries(col.sample_values)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 100)
      .map(([val]) => val);
  }, [columns]);

  // Track last reported row count to avoid duplicate calls
  const lastReportedRowsRef = useRef<number | null>(null);

  const fetchPreview = useCallback(async () => {
    // Check if we have a combined pre-split dataset ID
    const combinedDatasetId = sessionStorage.getItem('combined_presplit_dataset_id');
    
    // For pre-split mode with combined dataset, we don't need a file
    const hasValidSource = combinedDatasetId || selectedDataSources[0]?.file;
    
    if (groups.length === 0 || !hasValidSource || !targetVariable) {
      setWaterfall([]);
      setWarnings([]);
      // Reset to original row count when no exclusion rules
      if (onFilteredRowsChange && originalRowCount != null) {
        if (lastReportedRowsRef.current !== originalRowCount) {
          lastReportedRowsRef.current = originalRowCount;
          onFilteredRowsChange(originalRowCount);
        }
      }
      return;
    }

    setIsLoading(true);
    try {
      let result;
      
      if (combinedDatasetId) {
        // Use the combined dataset ID for pre-split mode
        console.log(`📊 Exclusion preview using combined dataset: ${combinedDatasetId}`);
        result = await fastApiService.getExclusionPreviewById(
          combinedDatasetId,
          groups,
          targetVariable
        );
      } else {
        // Use file upload for platform split mode
        result = await fastApiService.getExclusionPreview(
          selectedDataSources[0].file,
          groups,
          targetVariable
        );
      }
      
      setWaterfall(result.waterfall);
      setWarnings(result.warnings);
      // Report filtered row count to parent (only if changed)
      if (result.waterfall.length > 0 && onFilteredRowsChange) {
        const lastRow = result.waterfall[result.waterfall.length - 1];
        if (lastReportedRowsRef.current !== lastRow.remaining) {
          lastReportedRowsRef.current = lastRow.remaining;
          onFilteredRowsChange(lastRow.remaining);
        }
      }
    } catch (err) {
      console.error('Exclusion preview failed:', err);
    } finally {
      setIsLoading(false);
    }
  }, [groups, selectedDataSources, targetVariable, onFilteredRowsChange, originalRowCount]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      if (groups.length > 0 && groups.some(g => g.conditions.length > 0)) {
        fetchPreview();
      }
    }, 500);
    return () => clearTimeout(debounce);
  }, [groups, fetchPreview]);

  useEffect(() => {
    onExclusionRulesChange?.(groups);
  }, [groups, onExclusionRulesChange]);

  const addGroup = () => {
    setGroups(prev => [...prev, createEmptyGroup(columns)]);
  };

  const removeGroup = (groupId: string) => {
    setGroups(prev => prev.filter(g => g.id !== groupId));
  };

  const addCondition = (groupId: string) => {
    setGroups(prev =>
      prev.map(g =>
        g.id === groupId
          ? { ...g, conditions: [...g.conditions, createEmptyCondition(columns)] }
          : g
      )
    );
  };

  const removeCondition = (groupId: string, conditionId: string) => {
    setGroups(prev =>
      prev.map(g => {
        if (g.id !== groupId) return g;
        const newConditions = g.conditions.filter(c => c.id !== conditionId);
        return newConditions.length === 0 ? g : { ...g, conditions: newConditions };
      })
    );
  };

  const updateCondition = (
    groupId: string,
    conditionId: string,
    updates: Partial<ExclusionCondition>
  ) => {
    setGroups(prev =>
      prev.map(g => {
        if (g.id !== groupId) return g;
        return {
          ...g,
          conditions: g.conditions.map(c => {
            if (c.id !== conditionId) return c;
            const updated = { ...c, ...updates };
            if (updates.column && !updates.columnType) {
              const col = columns.find(col => col.name === updates.column);
              if (col) {
                updated.columnType = getColumnType(col);
                updated.operator = OPERATORS_BY_TYPE[updated.columnType][0]?.value || '=';
                updated.value = null;
              }
            }
            if (updates.operator) {
              if (updates.operator.includes('NULL')) {
                updated.value = null;
              }
            }
            return updated;
          }),
        };
      })
    );
  };

  const toggleConnector = (groupId: string, conditionId: string) => {
    updateCondition(groupId, conditionId, {
      connector: groups
        .find(g => g.id === groupId)
        ?.conditions.find(c => c.id === conditionId)?.connector === 'AND'
        ? 'OR'
        : 'AND',
    });
  };

  const renderValueInput = (group: ExclusionGroup, condition: ExclusionCondition) => {
    const { operator, columnType, column, value } = condition;

    if (operator.includes('NULL')) {
      return (
        <span className="text-gray-400 dark:text-gray-500 italic text-sm px-3 py-2">No value needed</span>
      );
    }

    if (operator === 'BETWEEN' || operator === 'NOT BETWEEN') {
      const [min, max] = Array.isArray(value) ? value : ['', ''];
      return (
        <div className="flex items-center gap-2">
          <input
            type={columnType === 'Date' ? 'date' : 'number'}
            value={min || ''}
            onChange={e => updateCondition(group.id, condition.id, { value: [e.target.value, max] })}
            className="w-28 px-2 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
            placeholder="Min"
          />
          <span className="text-gray-500 dark:text-gray-400 text-sm">and</span>
          <input
            type={columnType === 'Date' ? 'date' : 'number'}
            value={max || ''}
            onChange={e => updateCondition(group.id, condition.id, { value: [min, e.target.value] })}
            className="w-28 px-2 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
            placeholder="Max"
          />
        </div>
      );
    }

    if (operator === 'IN' || operator === 'NOT IN') {
      const vals = Array.isArray(value) ? value.join(', ') : (value as string) || '';
      return (
        <input
          type="text"
          value={vals}
          onChange={e => {
            const arr = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
            updateCondition(group.id, condition.id, { value: arr.length > 0 ? arr : e.target.value });
          }}
          placeholder="Value1, Value2, ..."
          className="flex-1 min-w-[180px] px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
        />
      );
    }

    if (columnType === 'Boolean') {
      return null;
    }

    if (columnType === 'Date') {
      return (
        <input
          type="date"
          value={(value as string) || ''}
          onChange={e => updateCondition(group.id, condition.id, { value: e.target.value })}
          className="w-40 px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
        />
      );
    }

    if (columnType === 'Numeric') {
      return (
        <input
          type="number"
          value={(value as number) ?? ''}
          onChange={e => updateCondition(group.id, condition.id, { value: e.target.value ? Number(e.target.value) : null })}
          className="w-32 px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
          placeholder="Value"
        />
      );
    }

    const topVals = getTopValues(column);
    if ((operator === '=' || operator === '!=') && topVals.length > 0) {
      return (
        <select
          value={(value as string) || ''}
          onChange={e => updateCondition(group.id, condition.id, { value: e.target.value })}
          className="flex-1 min-w-[150px] px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
        >
          <option value="">Select value...</option>
          {topVals.map(v => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      );
    }

    return (
      <input
        type="text"
        value={(value as string) || ''}
        onChange={e => updateCondition(group.id, condition.id, { value: e.target.value })}
        className="flex-1 min-w-[150px] px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm"
        placeholder="Value"
      />
    );
  };

  const hasBlockingWarning = warnings.some(w => w.level === 'block');

  if (!datasetAnalysis) return null;

  return (
    <div className="md:col-span-2 lg:col-span-3 space-y-4">
      <div className="flex items-center gap-2">
        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Exclusion Rules <span className="font-normal">(optional)</span>
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
        {groups.map((group, groupIndex) => (
          <React.Fragment key={group.id}>
            {groupIndex > 0 && (
              <div className="flex items-center justify-center py-2">
                <span className="text-orange-500 font-semibold text-sm">OR</span>
              </div>
            )}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-[#1e3a5f] dark:bg-blue-700 text-white text-xs font-semibold rounded">
                    GROUP {groupIndex + 1}
                  </span>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Conditions joined by AND/OR (your choice)
                  </span>
                </div>
                {groups.length > 1 && (
                  <button
                    onClick={() => removeGroup(group.id)}
                    className="text-gray-400 dark:text-gray-500 hover:text-red-500 transition-colors"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              <div className="space-y-3">
                {group.conditions.map((condition, condIndex) => {
                  const colType = condition.columnType;
                  const operators = OPERATORS_BY_TYPE[colType] || OPERATORS_BY_TYPE.Categorical;

                  const connectorKey = `${group.id}-${condIndex - 1}`;
                  return (
                    <div key={condition.id} className="flex items-center gap-2 flex-wrap">
                      {condIndex > 0 && (
                        <div className="relative" ref={openConnectorDropdown === connectorKey ? connectorDropdownRef : null}>
                          <button
                            onClick={() => setOpenConnectorDropdown(
                              openConnectorDropdown === connectorKey ? null : connectorKey
                            )}
                            className="flex items-center gap-1 px-2 py-0.5 bg-[#1e3a5f] dark:bg-blue-700 text-white text-xs font-semibold rounded cursor-pointer hover:bg-[#2a4a6f] dark:hover:bg-blue-600 transition-colors"
                          >
                            <span>{group.conditions[condIndex - 1].connector}</span>
                            <ChevronDown size={12} />
                          </button>
                          {openConnectorDropdown === connectorKey && (
                            <div className="absolute z-50 mt-1 w-20 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
                              <button
                                onClick={() => {
                                  updateCondition(group.id, group.conditions[condIndex - 1].id, { connector: 'AND' });
                                  setOpenConnectorDropdown(null);
                                }}
                                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 ${
                                  group.conditions[condIndex - 1].connector === 'AND' ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-medium' : ''
                                }`}
                              >
                                AND
                              </button>
                              <button
                                onClick={() => {
                                  updateCondition(group.id, group.conditions[condIndex - 1].id, { connector: 'OR' });
                                  setOpenConnectorDropdown(null);
                                }}
                                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 ${
                                  group.conditions[condIndex - 1].connector === 'OR' ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-medium' : ''
                                }`}
                              >
                                OR
                              </button>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="relative" ref={openColumnDropdown === condition.id ? columnDropdownRef : null}>
                        <button
                          onClick={() => {
                            if (openColumnDropdown === condition.id) {
                              setOpenColumnDropdown(null);
                              setColumnSearchQuery('');
                            } else {
                              setOpenColumnDropdown(condition.id);
                              setColumnSearchQuery('');
                            }
                          }}
                          className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-gray-200 text-sm min-w-[140px]"
                        >
                          <span className="truncate">{condition.column || 'Select column'}</span>
                          <ChevronDown size={14} className="text-gray-400 flex-shrink-0" />
                        </button>
                        {openColumnDropdown === condition.id && (
                          <div className="absolute z-50 mt-1 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
                            {/* Search input */}
                            <div className="p-2 border-b border-gray-200 dark:border-gray-700">
                              <input
                                type="text"
                                value={columnSearchQuery}
                                onChange={(e) => setColumnSearchQuery(e.target.value)}
                                placeholder="Search by name or type..."
                                className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                autoFocus
                                onClick={(e) => e.stopPropagation()}
                              />
                            </div>
                            {/* Column list */}
                            <div className="max-h-52 overflow-auto">
                              {filteredColumns.length === 0 ? (
                                <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                                  No columns found
                                </div>
                              ) : (
                                filteredColumns.map(col => (
                                  <button
                                    key={col.name}
                                    onClick={() => {
                                      updateCondition(group.id, condition.id, { column: col.name });
                                      setOpenColumnDropdown(null);
                                      setColumnSearchQuery('');
                                    }}
                                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 flex justify-between items-center"
                                  >
                                    <span className="truncate">{col.name}</span>
                                    <span className="text-xs text-gray-400 dark:text-gray-500 ml-2 flex-shrink-0">
                                      {getColumnType(col)}
                                    </span>
                                  </button>
                                ))
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="relative" ref={openOperatorDropdown === condition.id ? operatorDropdownRef : null}>
                        <button
                          onClick={() => setOpenOperatorDropdown(
                            openOperatorDropdown === condition.id ? null : condition.id
                          )}
                          className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-gray-200 text-sm min-w-[100px]"
                        >
                          <span>{condition.operator}</span>
                          <ChevronDown size={14} className="text-gray-400 dark:text-gray-500" />
                        </button>
                        {openOperatorDropdown === condition.id && (
                          <div className="absolute z-50 mt-1 w-36 max-h-60 overflow-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
                            {operators.map(op => (
                              <button
                                key={op.value}
                                onClick={() => {
                                  updateCondition(group.id, condition.id, { operator: op.value });
                                  setOpenOperatorDropdown(null);
                                }}
                                className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 ${
                                  condition.operator === op.value ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-medium' : ''
                                }`}
                              >
                                {op.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      {renderValueInput(group, condition)}

                      {group.conditions.length > 1 && (
                        <button
                          onClick={() => removeCondition(group.id, condition.id)}
                          className="text-gray-400 dark:text-gray-500 hover:text-red-500 transition-colors p-1"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              <button
                onClick={() => addCondition(group.id)}
                className="mt-3 text-orange-500 text-sm font-medium hover:text-orange-600 flex items-center gap-1"
              >
                <Plus size={14} />
                Add condition
              </button>
            </div>
          </React.Fragment>
        ))}

        <button
          onClick={addGroup}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          <Plus size={16} />
          Add group
        </button>

        {warnings.length > 0 && (
          <div className="space-y-2">
            {warnings.map((w, i) => (
              <div
                key={i}
                className={`flex items-start gap-2 p-3 rounded-lg text-sm ${
                  w.level === 'block'
                    ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                    : w.level === 'red'
                    ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-300 border border-red-200 dark:border-red-800'
                    : 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700'
                }`}
              >
                {w.level === 'block' ? (
                  <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
                )}
                <span>{w.message}</span>
              </div>
            ))}
          </div>
        )}

        {waterfall.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400 text-xs font-semibold uppercase">
                  <th className="text-left px-4 py-2">Step</th>
                  <th className="text-left px-4 py-2">Rule</th>
                  <th className="text-right px-4 py-2">Removed</th>
                  <th className="text-right px-4 py-2">Remaining</th>
                  <th className="text-right px-4 py-2">Event Rate</th>
                </tr>
              </thead>
              <tbody>
                {waterfall.map((row, i) => (
                  <tr
                    key={i}
                    className={`border-b border-gray-100 dark:border-gray-700 ${
                      row.step === 'Final' ? 'font-semibold bg-gray-50 dark:bg-gray-700/50' : ''
                    }`}
                  >
                    <td className="px-4 py-2 dark:text-gray-200">{row.step}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{row.label || (row.step === 'Start' ? 'Full population' : '')}</td>
                    <td className={`px-4 py-2 text-right dark:text-gray-200 ${
                      typeof row.removed === 'number' && row.removed < 0
                        ? 'text-red-500 dark:text-red-400 font-medium'
                        : ''
                    }`}>
                      {typeof row.removed === 'number' ? row.removed.toLocaleString() : row.removed}
                    </td>
                    <td className="px-4 py-2 text-right font-medium dark:text-gray-100">
                      {row.remaining.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right text-orange-500 dark:text-orange-400 font-medium">
                      {row.eventRate !== null ? `${row.eventRate.toFixed(2)}%` : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {isLoading && (
          <div className="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
            Calculating exclusion impact...
          </div>
        )}
      </div>
    </div>
  );
};

export default ExclusionRulesPanel;
