import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Info, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { fastApiService } from '../services/fastApiService';

// Types
export type ReasonBadge = 'Leakage' | 'Identifier' | 'Low-value' | 'Flagged' | 'Clean';

export interface VariableReviewRow {
  variable: string;
  auc: string;
  auc_value: number | null;
  flags: string;
  reason: ReasonBadge;
  pre_selected: boolean;
  row_class: 'row-preselected' | 'row-flagged' | 'row-clean';
  detail_reasons: string[];
  layer_flags: string[];
  cardinality_ratio?: number;
  null_rate?: number;
  null_rate_diff?: number;
}

export interface VariableReviewSummary {
  total: number;
  pre_selected: number;
  flagged: number;
  clean: number;
}

export interface VariableReviewResponse {
  success: boolean;
  message: string;
  rows: VariableReviewRow[];
  summary: VariableReviewSummary | null;
  pipeline_time_ms: number | null;
}

interface VariableReviewPanelProps {
  /** The uploaded file to analyze (used before submission) */
  file?: File | null;
  /** Dataset ID (used after submission - if provided, file is ignored) */
  datasetId?: string | null;
  targetVariable: string;
  sampleIdVariable?: string | null;
  weightVariable?: string | null;
  /** Data dictionary file for LLM reasoning (optional) */
  dataDictionaryFile?: File | null;
  onApply: (removedVariables: string[]) => void;
  onProceedWithoutRemoving: () => void;
  onClose?: () => void;
}

// Audit trail entry for variable review actions
interface AuditTrailEntry {
  timestamp: string;
  action: 'override_keep' | 'manual_remove' | 'apply_removals' | 'proceed_without_removing';
  variable?: string;
  originalPreSelected?: boolean;
  details?: string;
}

const VariableReviewPanel: React.FC<VariableReviewPanelProps> = ({
  file,
  datasetId,
  targetVariable,
  sampleIdVariable,
  weightVariable,
  dataDictionaryFile,
  onApply,
  onProceedWithoutRemoving,
  onClose,
}) => {
  const [data, setData] = useState<VariableReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selections, setSelections] = useState<Record<string, boolean>>({});
  const [showAll, setShowAll] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [auditTrail, setAuditTrail] = useState<AuditTrailEntry[]>([]);

  // Fetch variable review data
  const fetchData = useCallback(async () => {
    if (!targetVariable) return;
    if (!file && !datasetId) return;

    setIsLoading(true);
    setError(null);

    try {
      let response: VariableReviewResponse;

      if (file) {
        // Use file-based preview (before submission)
        // Pass data dictionary for LLM reasoning touchpoints
        response = await fastApiService.getVariableReviewPreview(
          file,
          targetVariable,
          sampleIdVariable,
          weightVariable,
          null, // dataDictionary string
          dataDictionaryFile, // dataDictionaryFile
          true // enableLlmReasoning
        );
      } else if (datasetId) {
        // Use dataset-based review (after submission)
        response = await fastApiService.runVariableReview({
          dataset_id: datasetId,
          target_col: targetVariable,
          sample_id_col: sampleIdVariable || undefined,
          weight_col: weightVariable || undefined,
        });
      } else {
        return;
      }

      setData(response);

      // Initialize selections from pre_selected values
      const initialSelections: Record<string, boolean> = {};
      response.rows.forEach((row) => {
        initialSelections[row.variable] = row.pre_selected;
      });
      setSelections(initialSelections);
    } catch (err: any) {
      console.error('Variable review failed:', err);
      setError(err.message || 'Failed to run variable review');
    } finally {
      setIsLoading(false);
    }
  }, [file, datasetId, targetVariable, sampleIdVariable, weightVariable]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter visible rows
  const visibleRows = useMemo(() => {
    if (!data?.rows) return [];
    if (showAll) return data.rows;
    return data.rows.filter(
      (row) => row.pre_selected || row.reason === 'Flagged'
    );
  }, [data?.rows, showAll]);

  // Handle checkbox change with audit trail logging
  const handleCheckboxChange = (variable: string) => {
    const row = data?.rows.find(r => r.variable === variable);
    const currentSelection = selections[variable];
    const newSelection = !currentSelection;
    
    // Log to audit trail
    const entry: AuditTrailEntry = {
      timestamp: new Date().toISOString(),
      action: row?.pre_selected && !newSelection ? 'override_keep' : 'manual_remove',
      variable,
      originalPreSelected: row?.pre_selected,
      details: row?.pre_selected && !newSelection
        ? `User unchecked pre-selected variable "${variable}" (${row?.reason}) - Override: keeping variable`
        : newSelection
        ? `User checked variable "${variable}" for removal`
        : `User unchecked variable "${variable}" - keeping variable`,
    };
    
    setAuditTrail(prev => [...prev, entry]);
    console.log('[Audit Trail]', entry);
    
    setSelections((prev) => ({
      ...prev,
      [variable]: newSelection,
    }));
  };

  // Build audit summary for the final action
  const buildAuditSummary = (action: 'apply' | 'skip') => {
    const preSelectedVars = data?.rows.filter(r => r.pre_selected).map(r => r.variable) || [];
    const finalSelections = Object.entries(selections).filter(([_, selected]) => selected).map(([v]) => v);
    
    // Variables that were pre-selected but user unchecked (overrides)
    const overriddenToKeep = preSelectedVars.filter(v => !selections[v]);
    
    // Variables that were NOT pre-selected but user checked (manual additions)
    const manuallyAdded = finalSelections.filter(v => !preSelectedVars.includes(v));
    
    return {
      action,
      timestamp: new Date().toISOString(),
      totalVariables: data?.summary?.total || 0,
      preSelectedCount: preSelectedVars.length,
      finalRemovalCount: finalSelections.length,
      overriddenToKeep,
      manuallyAdded,
      removedVariables: finalSelections,
    };
  };

  // Handle apply
  const handleApply = async () => {
    const selectedForRemoval = Object.entries(selections)
      .filter(([_, isSelected]) => isSelected)
      .map(([variable]) => variable);

    // Log final action to audit trail
    const auditSummary = buildAuditSummary('apply');
    const finalEntry: AuditTrailEntry = {
      timestamp: new Date().toISOString(),
      action: 'apply_removals',
      details: `Applied removal of ${selectedForRemoval.length} variables. ` +
        `Overrides (kept): ${auditSummary.overriddenToKeep.length}, ` +
        `Manual additions: ${auditSummary.manuallyAdded.length}`,
    };
    
    const fullAuditTrail = [...auditTrail, finalEntry];
    console.log('[Audit Trail - Final Summary]', auditSummary);
    console.log('[Audit Trail - Full Log]', fullAuditTrail);
    
    // Store audit trail in sessionStorage
    try {
      sessionStorage.setItem('variable_review_audit_trail', JSON.stringify({
        summary: auditSummary,
        trail: fullAuditTrail,
      }));
    } catch (e) {
      console.error('Failed to save audit trail:', e);
    }

    if (selectedForRemoval.length === 0) {
      onProceedWithoutRemoving();
      return;
    }

    // If we're working with a file (before submission), just pass the selections back
    // The actual removal will happen during dataset upload
    if (file) {
      onApply(selectedForRemoval);
      return;
    }

    // If we have a datasetId (after submission), apply removal on the backend
    if (datasetId) {
      setIsApplying(true);
      try {
        await fastApiService.applyVariableRemoval({
          dataset_id: datasetId,
          variables_to_remove: selectedForRemoval,
        });
        onApply(selectedForRemoval);
      } catch (err: any) {
        console.error('Apply variable removal failed:', err);
        setError(err.message || 'Failed to apply variable removal');
      } finally {
        setIsApplying(false);
      }
    }
  };

  // Handle proceed without removing (with audit logging)
  const handleProceedWithoutRemoving = () => {
    const auditSummary = buildAuditSummary('skip');
    const preSelectedCount = data?.rows.filter(r => r.pre_selected).length || 0;
    
    const finalEntry: AuditTrailEntry = {
      timestamp: new Date().toISOString(),
      action: 'proceed_without_removing',
      details: `User chose to proceed without removing any variables. ` +
        `${preSelectedCount} variables were pre-selected for removal but user overrode this decision.`,
    };
    
    const fullAuditTrail = [...auditTrail, finalEntry];
    console.log('[Audit Trail - Override: Proceed Without Removing]', auditSummary);
    console.log('[Audit Trail - Full Log]', fullAuditTrail);
    
    // Store audit trail in sessionStorage
    try {
      sessionStorage.setItem('variable_review_audit_trail', JSON.stringify({
        summary: auditSummary,
        trail: fullAuditTrail,
      }));
    } catch (e) {
      console.error('Failed to save audit trail:', e);
    }
    
    onProceedWithoutRemoving();
  };

  // Toggle row expansion
  const toggleRowExpansion = (variable: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(variable)) {
        next.delete(variable);
      } else {
        next.add(variable);
      }
      return next;
    });
  };

  const selectedCount = Object.values(selections).filter(Boolean).length;

  // Render reason badge
  const renderReasonBadge = (reason: ReasonBadge) => {
    const badgeStyles: Record<ReasonBadge, string> = {
      Leakage: 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400',
      Identifier: 'bg-gray-800 dark:bg-gray-600 text-white',
      'Low-value': 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
      Flagged: 'text-amber-600 dark:text-amber-400 font-semibold',
      Clean: 'text-gray-400 dark:text-gray-500',
    };

    return (
      <span className={`px-3 py-1 rounded text-xs font-medium ${badgeStyles[reason]}`}>
        {reason}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-8">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-500 dark:border-orange-400 mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Running...</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">This may take a few seconds</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 text-sm text-orange-500 hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* Summary Banner */}
      <div className="mx-6 my-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <Info size={16} className="text-blue-500 dark:text-blue-400 flex-shrink-0" />
          <span className="text-sm text-blue-800 dark:text-blue-200">
            6-layer detection pipeline ran in{' '}
            {data.pipeline_time_ms ? (data.pipeline_time_ms / 1000).toFixed(1) : '0'}s.{' '}
            <strong>{data.summary?.pre_selected || 0} variables</strong> pre-selected for removal.{' '}
            <strong>{data.summary?.flagged || 0}</strong> flagged for review.
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400 text-xs font-semibold uppercase">
              <th className="w-12 px-4 py-3"></th>
              <th className="text-left px-4 py-3">Variable</th>
              <th className="text-right px-4 py-3">Reason</th>
              <th className="w-10 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const isExpanded = expandedRows.has(row.variable);
              const rowBgClass =
                row.row_class === 'row-preselected'
                  ? 'bg-red-50 dark:bg-red-900/20'
                  : row.row_class === 'row-flagged'
                  ? 'bg-amber-50 dark:bg-amber-900/20'
                  : 'bg-white dark:bg-gray-800';

              return (
                <React.Fragment key={row.variable}>
                  <tr
                    className={`border-b border-gray-100 dark:border-gray-700 ${rowBgClass} hover:bg-opacity-75 transition-colors`}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selections[row.variable] || false}
                        onChange={() => handleCheckboxChange(row.variable)}
                        className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-orange-500 focus:ring-orange-500 cursor-pointer"
                        style={{ accentColor: '#f97316' }}
                      />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                      {row.variable}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {renderReasonBadge(row.reason)}
                    </td>
                    <td className="px-4 py-3">
                      {row.detail_reasons.length > 0 && (
                        <button
                          onClick={() => toggleRowExpansion(row.variable)}
                          className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronUp size={16} />
                          ) : (
                            <ChevronDown size={16} />
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                  {isExpanded && row.detail_reasons.length > 0 && (
                    <tr className={`${rowBgClass} border-b border-gray-100 dark:border-gray-700`}>
                      <td></td>
                      <td colSpan={3} className="px-4 py-3">
                        <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1 pl-4 border-l-2 border-gray-300 dark:border-gray-600">
                          {row.detail_reasons.map((reason, idx) => (
                            <div key={idx}>• {reason}</div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Show All Link */}
      <div className="text-center py-4 border-t border-gray-100 dark:border-gray-700">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          Showing {visibleRows.length} of {data.summary?.total || 0} variables.{' '}
        </span>
        <button
          onClick={() => setShowAll(!showAll)}
          className="text-sm text-blue-500 dark:text-blue-400 hover:text-blue-600 dark:hover:text-blue-300 hover:underline"
        >
          {showAll ? 'Show less' : 'Show all'}
        </button>
      </div>

      {/* Action Buttons */}
      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
        <button
          onClick={handleProceedWithoutRemoving}
          disabled={isApplying}
          className="px-5 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          Proceed without removing
        </button>
        <button
          onClick={handleApply}
          disabled={isApplying}
          className="px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {isApplying ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Applying...
            </>
          ) : (
            `Apply and proceed${selectedCount > 0 ? ` (${selectedCount})` : ''}`
          )}
        </button>
      </div>
    </div>
  );
};

export default VariableReviewPanel;
