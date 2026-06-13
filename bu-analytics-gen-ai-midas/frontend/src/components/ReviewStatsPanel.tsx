import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { fastApiService, type PartitionPreviewResponse } from '../services/fastApiService';
import type { SplitConfiguration } from '../utils/partitionSplitConfig';

type FilePartitionRole = 'full' | 'train' | 'test' | 'oot';

const SECTION_LABEL = 'text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide';

function readDatasetConfig(): Record<string, unknown> {
  try {
    const raw = sessionStorage.getItem('dataset_config');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function getSplitConfigFromSession(): SplitConfiguration | null {
  const cfg = readDatasetConfig();
  const d = cfg.split_configuration as SplitConfiguration | undefined;
  if (d && typeof d === 'object' && d.ingestion_mode === 'platform_split') {
    return d;
  }
  return null;
}

const PARTITION_HEADER: Record<string, string> = {
  train: 'Train',
  test: 'Test',
  validation: 'Validation',
};

const PRE_SPLIT_ORDER: FilePartitionRole[] = ['train', 'test', 'oot'];
const PRE_SPLIT_HEADER: Record<FilePartitionRole, string> = {
  full: 'Full population',
  train: 'Train',
  test: 'Test',
  oot: 'Validation',
};

interface UploadRowLite {
  id: string;
  role?: FilePartitionRole;
  rowCount?: number;
  colCount?: number;
  isAnalyzing?: boolean;
  file?: File;
  fileName?: string;
}

interface PreSplitAdjustedStats {
  role: FilePartitionRole;
  originalRowCount: number;
  adjustedRowCount: number;
  originalColCount: number;
  adjustedColCount: number;
  eventRate?: number | null;
  eventCount?: number | null;
  nonEventCount?: number | null;
  fileName?: string;
}

interface ReviewStatsPanelProps {
  workflowPath: 'platform_split' | 'pre_split' | 'conflict' | null;
  datasetAnalysis: {
    totalRows: number;
    totalColumns: number;
    columns: { name: string; type?: string; logical_type?: string }[];
  } | null; // optional for pre-split row-count-only view
  selectedDataSources: any[];
  targetVariable: string;
  uploadedRows: UploadRowLite[];
  schemaMatch: boolean;
  activeDatasetId?: string | null;
  /** When set (e.g. immediately after submit), partition preview uses server data without waiting on activeDatasetId. */
  pendingDatasetId?: string | null;
}

const ReviewStatsPanel: React.FC<ReviewStatsPanelProps> = ({
  workflowPath,
  datasetAnalysis,
  selectedDataSources,
  targetVariable,
  uploadedRows,
  schemaMatch,
  activeDatasetId,
  pendingDatasetId = null,
}) => {
  const serverDatasetId = activeDatasetId ?? pendingDatasetId ?? null;
  const [preview, setPreview] = useState<PartitionPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Pre-split adjusted stats after exclusion rules and variable removal
  const [preSplitAdjustedStats, setPreSplitAdjustedStats] = useState<PreSplitAdjustedStats[]>([]);
  const [preSplitLoading, setPreSplitLoading] = useState(false);

  const platformFile = useMemo(() => {
    const full = selectedDataSources.find((s) => s?.type === 'file' && s.partitionRole === 'full' && s.file instanceof File);
    if (full?.file) return full.file as File;
    const anyF = selectedDataSources.find((s) => s?.type === 'file' && s.file instanceof File);
    return (anyF?.file as File) || null;
  }, [selectedDataSources]);

  const runPlatformPreview = useCallback(async () => {
    if (workflowPath !== 'platform_split') {
      setPreview(null);
      setError(null);
      return;
    }
    // Need either server dataset id (optimized path) or platformFile (fallback)
    if (!serverDatasetId && !platformFile) {
      setPreview(null);
      setError(null);
      return;
    }
    if (!targetVariable?.trim()) {
      setPreview(null);
      setError(null);
      return;
    }
    const sc = getSplitConfigFromSession();
    if (!sc) {
      setPreview(null);
      return;
    }
    if (sc.split_method === 'user_identifier') {
      if (!sc.identifier_column || !sc.identifier_mapping?.train) {
        setPreview(null);
        setError(null);
        return;
      }
    }
    setLoading(true);
    setError(null);
    try {
      // Get exclusion rules and variables to remove from sessionStorage
      const cfg = readDatasetConfig();
      const exclusionRules = cfg.exclusion_rules as Array<{
        id: string;
        conditions: Array<{
          column: string;
          operator: string;
          value: string | number | string[] | [number, number] | null;
          connector: 'AND' | 'OR';
        }>;
      }> | undefined;
      const variablesToRemove = cfg.variables_to_remove as string[] | undefined;

      let result;
      if (serverDatasetId) {
        result = await fastApiService.partitionPreviewById({
          dataset_id: serverDatasetId,
          split_configuration: sc as unknown as Record<string, unknown>,
          target_variable: targetVariable.trim(),
          exclusion_rules: exclusionRules,
          variables_to_remove: variablesToRemove,
        });
      } else if (platformFile) {
        // The legacy multipart `/partition-preview` path used to re-upload
        // the entire file here. With chunked-upload finalize now eagerly
        // registering the dataset, `serverDatasetId` is always set the
        // moment the upload completes, so this branch is just the
        // "still uploading" / "upload errored" UI path.
        const row = uploadedRows.find(r => r.file === platformFile);
        if (row?.uploadError) {
          setError(`Upload failed for ${platformFile.name}. Please re-upload the file to compute preview.`);
          setLoading(false);
          return;
        }
        setError('Preparing dataset… preview will refresh as soon as the upload finishes.');
        setLoading(false);
        return;
      } else {
        setPreview(null);
        return;
      }
      setPreview(result);
    } catch (e: unknown) {
      setPreview(null);
      setError(e instanceof Error ? e.message : 'Preview failed');
    } finally {
      setLoading(false);
    }
  }, [workflowPath, platformFile, targetVariable, serverDatasetId, uploadedRows]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runPlatformPreview();
    }, 320);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [runPlatformPreview]);

  useEffect(() => {
    const onCfg = () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => void runPlatformPreview(), 120);
    };
    window.addEventListener('datasetConfigChanged', onCfg);
    return () => window.removeEventListener('datasetConfigChanged', onCfg);
  }, [runPlatformPreview]);

  // Compute adjusted stats for pre-split mode when exclusion rules or variable removal changes
  const computePreSplitAdjustedStats = useCallback(async () => {
    if (workflowPath !== 'pre_split') return;
    
    const cfg = readDatasetConfig();
    const exclusionRules = cfg.exclusion_rules as Array<{
      id: string;
      conditions: Array<{
        column: string;
        operator: string;
        value: string | number | string[] | [number, number] | null;
        connector: 'AND' | 'OR';
      }>;
    }> | undefined;
    const variablesToRemove = cfg.variables_to_remove as string[] | undefined;
    
    // Get files with roles from selectedDataSources
    const filesWithRoles = selectedDataSources.filter(
      (s) => s?.type === 'file' && s?.file instanceof File && ['train', 'test', 'oot'].includes(s.partitionRole)
    );
    
    // Also check uploadedRows for files
    const uploadedRowsWithFiles = uploadedRows.filter(
      (r) => r.role && r.rowCount != null && !r.isAnalyzing
    );
    
    if (filesWithRoles.length === 0 && uploadedRowsWithFiles.length === 0) return;
    
    // Always compute stats to get event counts for KPI cards
    
    setPreSplitLoading(true);
    
    try {
      const adjustedStats: PreSplitAdjustedStats[] = [];
      
      // Process each file with a role
      for (let idx = 0; idx < filesWithRoles.length; idx++) {
        const source = filesWithRoles[idx];
        const file = source.file as File;
        const role = source.partitionRole as FilePartitionRole;
        
        // For multiple files with same role (e.g., validation), find the corresponding uploadedRow
        const matchingRows = uploadedRows.filter((r) => r.role === role);
        const originalRow = matchingRows.length > 0 
          ? (role === 'oot' 
              ? matchingRows.find((r) => r.file?.name === file.name || r.fileName === file.name) || matchingRows[0]
              : matchingRows[0])
          : undefined;
        const originalRowCount = originalRow?.rowCount || 0;
        const originalColCount = originalRow?.colCount || 0;
        
        let adjustedRowCount = originalRowCount;
        let adjustedColCount = originalColCount;
        let eventRate: number | null = null;
        let eventCount: number | null = null;
        let nonEventCount: number | null = null;
        
        // If there are exclusion rules, call the exclusion preview API
        if (exclusionRules && exclusionRules.length > 0 && targetVariable?.trim()) {
          try {
            const exclusionResult = await fastApiService.getExclusionPreview(
              file,
              exclusionRules,
              targetVariable.trim()
            );
            
            // Get the final remaining count from the waterfall
            if (exclusionResult.waterfall && exclusionResult.waterfall.length > 0) {
              const lastStep = exclusionResult.waterfall[exclusionResult.waterfall.length - 1];
              adjustedRowCount = lastStep.remaining;
              eventRate = lastStep.eventRate;
              eventCount = lastStep.eventCount ?? null;
              nonEventCount = lastStep.nonEventCount ?? null;
            }
          } catch (e) {
            console.error(`Failed to get exclusion preview for ${role}:`, e);
          }
        } else if (targetVariable?.trim()) {
          // No exclusion rules, but we still need to get event stats from the file
          // Call exclusion preview with empty rules just to get event counts
          try {
            const result = await fastApiService.getExclusionPreview(
              file,
              [],
              targetVariable.trim()
            );
            if (result.waterfall && result.waterfall.length > 0) {
              const firstStep = result.waterfall[0];
              eventRate = firstStep.eventRate;
              eventCount = firstStep.eventCount ?? null;
              nonEventCount = firstStep.nonEventCount ?? null;
            }
          } catch (e) {
            console.error(`Failed to get event stats for ${role}:`, e);
          }
        }
        
        // Adjust column count if variables are removed
        if (variablesToRemove && variablesToRemove.length > 0) {
          adjustedColCount = Math.max(0, originalColCount - variablesToRemove.length);
        }
        
        adjustedStats.push({
          role,
          originalRowCount,
          adjustedRowCount,
          originalColCount,
          adjustedColCount,
          eventRate,
          eventCount,
          nonEventCount,
          fileName: file.name,
        });
      }
      
      setPreSplitAdjustedStats(adjustedStats);
      console.log('📊 Pre-split adjusted stats computed:', adjustedStats);
    } catch (e) {
      console.error('Failed to compute pre-split adjusted stats:', e);
    } finally {
      setPreSplitLoading(false);
    }
  }, [workflowPath, selectedDataSources, uploadedRows, targetVariable]);

  // Run pre-split adjusted stats computation when config changes
  useEffect(() => {
    if (workflowPath !== 'pre_split') return;
    
    const onCfg = () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => void computePreSplitAdjustedStats(), 300);
    };
    
    // Initial computation
    void computePreSplitAdjustedStats();
    
    window.addEventListener('datasetConfigChanged', onCfg);
    return () => window.removeEventListener('datasetConfigChanged', onCfg);
  }, [workflowPath, computePreSplitAdjustedStats]);

  const preSplitPartitions = useMemo(() => {
    if (workflowPath !== 'pre_split') return null;
    const tagged = uploadedRows.filter((r) => r.role && r.rowCount != null && !r.isAnalyzing);
    if (tagged.length === 0) return null;
    
    // Always use adjusted stats if available (they include event counts)
    const useAdjusted = preSplitAdjustedStats.length > 0;
    
    const adjustedTagged = tagged.map((row) => {
      if (!useAdjusted) return row;
      const adjusted = preSplitAdjustedStats.find((s) => s.role === row.role);
      if (!adjusted) return row;
      return {
        ...row,
        rowCount: adjusted.adjustedRowCount,
        colCount: adjusted.adjustedColCount,
        eventRate: adjusted.eventRate,
        eventCount: adjusted.eventCount,
        nonEventCount: adjusted.nonEventCount,
        originalRowCount: adjusted.originalRowCount,
        originalColCount: adjusted.originalColCount,
      };
    });
    
    // Aggregate multiple validation (oot) files into a single entry
    const ootRows = adjustedTagged.filter((r) => r.role === 'oot');
    const nonOotRows = adjustedTagged.filter((r) => r.role !== 'oot');
    
    let finalTagged = nonOotRows;
    if (ootRows.length > 0) {
      // Sum up all oot row stats
      const aggregatedOot = {
        ...ootRows[0],
        rowCount: ootRows.reduce((sum, r) => sum + (r.rowCount || 0), 0),
        colCount: ootRows[0].colCount,
        eventCount: ootRows.reduce((sum, r) => sum + (r.eventCount || 0), 0),
        nonEventCount: ootRows.reduce((sum, r) => sum + (r.nonEventCount || 0), 0),
        originalRowCount: ootRows.reduce((sum, r) => sum + (r.originalRowCount || r.rowCount || 0), 0),
        originalColCount: ootRows[0].originalColCount || ootRows[0].colCount,
        eventRate: null as number | null,
        fileName: ootRows.length > 1 
          ? `${ootRows.length} validation files (merged)` 
          : ootRows[0].fileName,
      };
      // Recalculate event rate from aggregated counts
      if (aggregatedOot.eventCount != null && aggregatedOot.rowCount) {
        aggregatedOot.eventRate = (aggregatedOot.eventCount / aggregatedOot.rowCount) * 100;
      }
      finalTagged = [...nonOotRows, aggregatedOot];
    }
    
    const total = finalTagged.reduce((s, r) => s + (r.rowCount as number), 0);
    const order = PRE_SPLIT_ORDER.filter((role) => finalTagged.some((t) => t.role === role));
    return { tagged: finalTagged, total, order };
  }, [workflowPath, uploadedRows, preSplitAdjustedStats]);

  if (workflowPath === 'conflict' || workflowPath === null) {
    return null;
  }

  if (workflowPath === 'pre_split' && !preSplitPartitions) {
    return null;
  }

  if (workflowPath === 'platform_split' && !datasetAnalysis) {
    return null;
  }

  return (
    <div className="md:col-span-2 lg:col-span-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 shadow-sm">
      <p className={`${SECTION_LABEL} mb-3`}>Review Stats</p>

      {workflowPath === 'platform_split' && datasetAnalysis && (
        <>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 py-6 justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
              Updating preview…
            </div>
          )}
          {error && !loading && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-900 dark:text-amber-200">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {preview && !loading && preview.success && (
            <PlatformPreviewBody preview={preview} />
          )}
          {!loading && !preview && !error && targetVariable?.trim() && (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-2">Configure partitioning above to see train / test / validation statistics.</p>
          )}
        </>
      )}

      {workflowPath === 'pre_split' && preSplitPartitions && (
        <div className="space-y-3">
          {!schemaMatch && preSplitPartitions.tagged.length > 1 && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-900 dark:text-red-200">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span>Schema validation failed - see errors above. Resolve column count, name, or type mismatches before proceeding.</span>
            </div>
          )}
          {preSplitLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 py-2">
              <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
              Updating stats with exclusion rules…
            </div>
          )}
          <PreSplitTable data={preSplitPartitions} targetVariable={targetVariable} />
        </div>
      )}
    </div>
  );
};

interface PreSplitRowData extends UploadRowLite {
  eventRate?: number | null;
  eventCount?: number | null;
  nonEventCount?: number | null;
  originalRowCount?: number;
  originalColCount?: number;
  fileName?: string;
}

function PreSplitTable({
  data,
  targetVariable,
}: {
  data: { tagged: PreSplitRowData[]; total: number; order: FilePartitionRole[] };
  targetVariable?: string;
}) {
  const { tagged, total, order } = data;

  // Calculate overall stats
  const totalRows = tagged.reduce((sum, r) => sum + (r.rowCount || 0), 0);
  const totalEvents = tagged.reduce((sum, r) => sum + (r.eventCount || 0), 0);
  const totalCols = tagged[0]?.colCount || 0;
  const overallEventRate = totalRows > 0 && totalEvents > 0 ? (totalEvents / totalRows) * 100 : null;

  return (
    <div className="space-y-5">
      {/* KPI Cards - same as platform_split */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard label="Total rows" value={totalRows.toLocaleString()} />
        <KpiCard
          label="Event rate"
          value={overallEventRate != null ? `${overallEventRate.toFixed(1)}%` : '-'}
        />
        <KpiCard label="Features" value={String(totalCols)} />
      </div>

      {/* Partition Table - same structure as platform_split */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left py-2 pr-4 font-medium text-gray-700 dark:text-gray-300">Metric</th>
              {order.map((role) => (
                <th key={role} className="text-right py-2 px-2 font-medium text-gray-700 dark:text-gray-300">
                  {PRE_SPLIT_HEADER[role]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Row count</td>
              {order.map((role) => {
                const row = tagged.find((t) => t.role === role) as PreSplitRowData | undefined;
                return (
                  <td key={role} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                    {row?.rowCount != null ? row.rowCount.toLocaleString() : '-'}
                  </td>
                );
              })}
            </tr>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Proportion</td>
              {order.map((role) => {
                const row = tagged.find((t) => t.role === role);
                const pct = row?.rowCount != null && total > 0 ? ((row.rowCount / total) * 100).toFixed(1) : '-';
                return (
                  <td key={role} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                    {pct === '-' ? '-' : `${pct}%`}
                  </td>
                );
              })}
            </tr>
            {targetVariable && (
              <>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Event count</td>
                  {order.map((role) => {
                    const row = tagged.find((t) => t.role === role) as PreSplitRowData | undefined;
                    return (
                      <td key={role} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                        {row?.eventCount != null ? row.eventCount.toLocaleString() : '-'}
                      </td>
                    );
                  })}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Event rate</td>
                  {order.map((role) => {
                    const row = tagged.find((t) => t.role === role) as PreSplitRowData | undefined;
                    return (
                      <td key={role} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                        {row?.eventRate != null ? `${row.eventRate.toFixed(2)}%` : '-'}
                      </td>
                    );
                  })}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Non-events</td>
                  {order.map((role) => {
                    const row = tagged.find((t) => t.role === role) as PreSplitRowData | undefined;
                    return (
                      <td key={role} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                        {row?.nonEventCount != null ? row.nonEventCount.toLocaleString() : '-'}
                      </td>
                    );
                  })}
                </tr>
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PlatformPreviewBody({ preview }: { preview: PartitionPreviewResponse }) {
  const parts = preview.partitions || [];
  const binary = preview.target_kind === 'binary';

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard label="Total rows" value={preview.total_rows.toLocaleString()} />
        <KpiCard
          label="Event rate"
          value={preview.overall_event_rate_pct != null ? `${preview.overall_event_rate_pct.toFixed(1)}%` : '-'}
        />
        <KpiCard label="Features" value={String(preview.features)} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left py-2 pr-4 font-medium text-gray-700 dark:text-gray-300">Metric</th>
              {parts.map((p) => (
                <th key={p.key} className="text-right py-2 px-2 font-medium text-gray-700 dark:text-gray-300">
                  {PARTITION_HEADER[p.key] || p.key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Row count</td>
              {parts.map((p) => (
                <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                  {p.row_count.toLocaleString()}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Proportion</td>
              {parts.map((p) => (
                <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                  {p.proportion_pct.toFixed(1)}%
                </td>
              ))}
            </tr>
            {binary && (
              <>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Event count</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.event_count != null ? p.event_count.toLocaleString() : '-'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Event rate</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.event_rate_pct != null ? `${p.event_rate_pct.toFixed(2)}%` : '-'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Non-events</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.non_event_count != null ? p.non_event_count.toLocaleString() : '-'}
                    </td>
                  ))}
                </tr>
              </>
            )}
            {preview.target_kind === 'regression' && (
              <>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Target mean</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.target_mean != null ? String(p.target_mean) : '-'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Target median</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.target_median != null ? String(p.target_median) : '-'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Target std dev</td>
                  {parts.map((p) => (
                    <td key={p.key} className="text-right py-2 px-2 tabular-nums dark:text-gray-200">
                      {p.target_std != null ? String(p.target_std) : '-'}
                    </td>
                  ))}
                </tr>
              </>
            )}
            {parts.some((p) => p.date_range) && (
              <tr>
                <td className="py-2 pr-4 text-gray-600 dark:text-gray-400">Date range (time-based)</td>
                {parts.map((p) => (
                  <td key={p.key} className="text-right py-2 px-2 text-gray-800 dark:text-gray-200">
                    {p.date_range || '-'}
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {preview.target_kind === 'multiclass' && (
        <p className="text-xs text-gray-600 dark:text-gray-400">
          Multi-class target: per-class counts are available in the raw preview response; summary table shows row counts and
          proportions by partition.
        </p>
      )}
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50 px-3 py-3">
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100 tabular-nums">{value}</p>
    </div>
  );
}

export default ReviewStatsPanel;
