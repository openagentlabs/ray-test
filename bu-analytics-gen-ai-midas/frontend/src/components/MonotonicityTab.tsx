import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle, LineChart, TrendingUp, Info, BarChart3 } from 'lucide-react';
import { EvaluationModel, ModelEvaluationData, MonotonicityResults } from '../types/modelEvaluation';
import PSICSIModal from './PSICSIModal';

interface MonotonicityTabProps {
  availableModels: EvaluationModel[];
  selectedModelIds: string[];
  evaluationData: Record<string, ModelEvaluationData>;
  loading?: boolean;
}

type DecileRow = {
  Decile: string | number;
  Count: number;
  Bads: number;
  Goods: number;
  Bad_Rate: number;
  Avg_Score: number;
  Lift: number;
  Cum_Bad_Rate: number;
};

const formatPct = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(2)}%`;
};

const formatNum = (value?: number | null, digits = 3) => {
  if (value === undefined || value === null || Number.isNaN(value)) return '-';
  return value.toFixed(digits);
};

const MonotonicityTab: React.FC<MonotonicityTabProps> = ({
  availableModels,
  selectedModelIds,
  evaluationData,
  loading = false,
}) => {
  const [modelId, setModelId] = useState<string | undefined>(selectedModelIds[0] || availableModels[0]?.id);
  const [isPSICSIModalOpen, setIsPSICSIModalOpen] = useState(false);

  useEffect(() => {
    // Always update modelId when available models change to ensure we have a valid model
    if (selectedModelIds.length > 0) {
      // If current modelId is not in the new selectedModelIds, update it
      if (!selectedModelIds.includes(modelId || '')) {
        setModelId(selectedModelIds[0]);
      }
    } else if (availableModels.length > 0) {
      const firstValidModel = availableModels.find((m) => m && m.id);
      if (firstValidModel && (!modelId || !availableModels.some(m => m.id === modelId))) {
        setModelId(firstValidModel.id);
      }
    }
  }, [selectedModelIds, availableModels, modelId]);

  const modelOptions = useMemo(() => {
    return availableModels
      .filter((m) => m && m.id)
      .map((m) => ({
        value: m.id,
        // Backend returns 'algorithm' field; fall back to 'name' for legacy data
        label: (m as any).algorithm || m.name || m.id,
      }));
  }, [availableModels]);

  const activeData = modelId ? evaluationData[modelId] : undefined;
  const monotonicity: MonotonicityResults | undefined =
    activeData?.monotonicity_results || activeData?.performance_metrics?.monotonicity_results;
  const monotonicityAny = monotonicity as (MonotonicityResults & Record<string, any>) | undefined;

  // Handle both simple (segmented) and advanced (global) monotonicity results
  const isAdvancedMonotonicity = !!monotonicityAny && Array.isArray(monotonicityAny.deciles) && monotonicityAny.deciles.length > 0;
  const isSimpleMonotonicity = !!monotonicityAny && !isAdvancedMonotonicity && Array.isArray(monotonicityAny.violations);

  // Extract data based on format - with additional safety checks
  const decilesData = useMemo<DecileRow[]>(() => {
    if (!monotonicityAny || !isAdvancedMonotonicity) return [];
    return (monotonicityAny.deciles || []) as DecileRow[];
  }, [isAdvancedMonotonicity, monotonicityAny]);
  
  const violationsData = useMemo<Array<Record<string, unknown>>>(() => {
    if (!monotonicityAny) return [];
    if (isAdvancedMonotonicity) {
      return (monotonicityAny.monotonicity_violations || []) as Array<Record<string, unknown>>;
    } else if (isSimpleMonotonicity) {
      return (monotonicityAny.violations || []) as Array<Record<string, unknown>>;
    }
    return [];
  }, [isAdvancedMonotonicity, isSimpleMonotonicity, monotonicityAny]);
  const monotonicityScore = monotonicityAny?.monotonicity_score || 0;
  const isMonotonic = monotonicityAny?.is_monotonic ?? monotonicityAny?.monotonicity_pass ?? true;

  // Check for import errors and log to console (Inspect tab)
  useEffect(() => {
    if (monotonicityAny?.error) {
      const errorInfo = monotonicityAny.error;
      console.error('🚨 Monotonicity Import Error:', errorInfo);
      console.error('Error Message:', typeof errorInfo === 'string' ? errorInfo : (errorInfo as Record<string, unknown>).message || errorInfo);
      console.error('Error Details:', typeof errorInfo === 'string' ? 'No additional details' : (errorInfo as Record<string, unknown>).details || 'No additional details available');
      console.error('This error occurred during model evaluation. The monotonicity utilities could not be imported.');
      console.error('Please check that monotonicity.py is properly deployed in backend/app/utils/');
    }
  }, [monotonicityAny]);

  const violationDeciles = useMemo(
    () => new Set<string | number>(violationsData.map((v: Record<string, unknown>) => {
      // Handle both advanced (decile) and simple (segment) violation formats
      if (isAdvancedMonotonicity) {
        return (v.to_decile as number | string);
      } else {
        // For simple monotonicity, use segment_to as the "decile" for highlighting
        return (v.segment_to as number | string);
      }
    })),
    [violationsData, isAdvancedMonotonicity],
  );

  const monotonicitySummaryLines = useMemo(() => {
    if (!decilesData.length) return [];
    return decilesData.map((row: DecileRow, idx: number) => {
      if (idx === 0) return null;
      const prev = decilesData[idx - 1];
      const status = row.Bad_Rate >= prev.Bad_Rate ? '✓' : '✗';
      return `Decile ${prev.Decile} → ${row.Decile}: ${formatPct(prev.Bad_Rate)} → ${formatPct(row.Bad_Rate)}  ${status}`;
    }).filter(Boolean) as string[];
  }, [decilesData]);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-lg font-semibold text-gray-900">Monotonicity & Rank Ordering</h4>
          <p className="text-sm text-gray-600">
            Decile bad-rate progression, KS, lift, and monotonicity violations.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {(monotonicity?.psi !== undefined && monotonicity?.psi !== null) || (monotonicity?.csi && monotonicity?.csi.length > 0) ? (
            <button
              onClick={() => setIsPSICSIModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 transition-colors font-medium text-sm shadow-sm"
            >
              <BarChart3 className="h-4 w-4" />
              View PSI & CSI
            </button>
          ) : null}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600 whitespace-nowrap">Model</label>
            <select
              className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[180px] max-w-xs"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              {modelOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="relative w-12 h-12">
              <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-200 rounded-full animate-ping opacity-75"></div>
              <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full animate-spin border-t-transparent"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-blue-600" />
              </div>
            </div>
            <p className="text-gray-700 font-medium text-sm">Loading monotonicity data...</p>
          </div>
        </div>
      )}

      {!loading && !monotonicity && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-600">
          No monotonicity results available for this model yet. Re-run model evaluation to compute decile,
          KS, and monotonicity diagnostics.
        </div>
      )}

      {!loading && monotonicity && (monotonicity as any).error && (
        <div className="rounded-lg border-2 border-red-300 bg-red-50 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h5 className="font-semibold text-red-900 mb-2">Monotonicity Import Error</h5>
              <p className="text-sm text-red-800 mb-2">
                The monotonicity utilities could not be imported during model evaluation. This is likely a deployment issue.
              </p>
              <details className="text-xs text-red-700">
                <summary className="cursor-pointer font-semibold mb-1 hover:text-red-900">
                  Technical Details (check browser console for full error)
                </summary>
                <div className="mt-2 pl-2 space-y-1 font-mono bg-red-100 p-2 rounded border border-red-200">
                  <div>Error: {(monotonicity as any).error.error || 'Unknown error'}</div>
                  {(monotonicity as any).error.message && (
                    <div className="text-[10px] break-all">{(monotonicity as any).error.message}</div>
                  )}
                </div>
              </details>
              <p className="text-xs text-red-600 mt-2 italic">
                Check the browser console (Inspect → Console) for detailed error information.
              </p>
            </div>
          </div>
        </div>
      )}

      {monotonicity && !(monotonicity as any).error && (
        <>
          {/* PSI Section at the top */}
          {monotonicity.psi !== undefined && monotonicity.psi !== null && (
            <div className="border border-purple-200 dark:border-slate-700 rounded-lg p-4 bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-purple-900 dark:text-purple-300">
                      <LineChart className="h-5 w-5 text-purple-600 dark:text-purple-300" />
                      Population Stability Index (PSI)
                    </div>
                    <div className="text-3xl font-bold text-purple-900 dark:text-purple-200">
                      {formatNum(monotonicity.psi, 4)}
                    </div>
                  </div>
                  <div className="text-xs text-purple-700 dark:text-purple-200 mb-3">
                    {monotonicity.psi < 0.1 ? (
                      <span className="font-semibold text-emerald-700">✓ Stable (PSI &lt; 0.1) - No significant population shift</span>
                    ) : monotonicity.psi < 0.25 ? (
                      <span className="font-semibold text-amber-700">⚠ Moderate shift (0.1 ≤ PSI &lt; 0.25) - Some population change detected</span>
                    ) : (
                      <span className="font-semibold text-red-700">⚠ Significant shift (PSI ≥ 0.25) - Major population change, investigate</span>
                    )}
                  </div>
                  <div className="border-t border-purple-200 dark:border-slate-700 pt-3 mt-3">
                    <details className="text-xs text-purple-800 dark:text-purple-200">
                      <summary className="cursor-pointer font-semibold flex items-center gap-1 hover:text-purple-900 dark:hover:text-purple-100">
                        <Info className="h-3 w-3" />
                        PSI Formula & Interpretation
                      </summary>
                      <div className="mt-2 pl-4 space-y-2 text-purple-700 dark:text-purple-200">
                        <div>
                          <div className="font-semibold mb-1">Formula:</div>
                          <div className="font-mono bg-white dark:bg-slate-900 px-2 py-1 rounded border border-purple-200 dark:border-slate-700">
                            PSI = Σ[(Actual% - Expected%) × ln(Actual% / Expected%)]
                          </div>
                        </div>
                        <div>
                          <div className="font-semibold mb-1">Where:</div>
                          <ul className="list-disc list-inside space-y-1 ml-2">
                            <li><strong>Expected%</strong> = percentage in each bin for training (reference) distribution</li>
                            <li><strong>Actual%</strong> = percentage in each bin for test (current) distribution</li>
                            <li>The sum is over all quantile bins (typically 10)</li>
                          </ul>
                        </div>
                        <div>
                          <div className="font-semibold mb-1">Interpretation:</div>
                          <ul className="list-disc list-inside space-y-1 ml-2">
                            <li><strong>PSI &lt; 0.1:</strong> No significant shift - model is stable</li>
                            <li><strong>0.1 ≤ PSI &lt; 0.25:</strong> Moderate shift - monitor closely</li>
                            <li><strong>PSI ≥ 0.25:</strong> Significant shift - investigate population changes</li>
                          </ul>
                        </div>
                        <div className="text-purple-600 dark:text-purple-300 italic">
                          PSI measures distribution shift between training and test predictions, helping detect population drift.
                        </div>
                      </div>
                    </details>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PSI Breakdown Table */}
          {monotonicity.psi_breakdown && monotonicity.psi_breakdown.length > 0 && (
            <div className="border border-purple-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
              <div className="mb-3">
                <h5 className="text-sm font-semibold text-purple-900 dark:text-purple-200 flex items-center gap-2">
                  <LineChart className="h-4 w-4" />
                  PSI Calculation Breakdown Table
                </h5>
                <p className="text-xs text-purple-700 dark:text-purple-300 mt-1">
                  Bin-by-bin breakdown showing Expected (Training) vs Actual (Test) distributions and PSI contributions
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-xs">
                  <thead className="bg-purple-50 dark:bg-slate-900">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-purple-900 dark:text-purple-200">Bin</th>
                      <th className="px-3 py-2 text-left font-semibold text-purple-900 dark:text-purple-200">Bin Range</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">Expected Count</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">Expected %</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">Actual Count</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">Actual %</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">Difference %</th>
                      <th className="px-3 py-2 text-right font-semibold text-purple-900 dark:text-purple-200">PSI Contribution</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-slate-800 bg-white dark:bg-slate-900/60">
                    {monotonicity.psi_breakdown.map((row, idx) => (
                      <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-slate-800">
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-200 font-medium">{row.Bin}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 font-mono text-[10px]">{row.Bin_Range}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 text-right">{row.Expected_Count.toLocaleString()}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 text-right">{formatPct(row.Expected_Pct)}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 text-right">{row.Actual_Count.toLocaleString()}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 text-right">{formatPct(row.Actual_Pct)}</td>
                        <td className={`px-3 py-2 text-right font-medium ${
                          row.Difference_Pct > 0 ? 'text-red-600' : row.Difference_Pct < 0 ? 'text-blue-600' : 'text-gray-600'
                        }`}>
                          {row.Difference_Pct > 0 ? '+' : ''}{formatPct(row.Difference_Pct)}
                        </td>
                        <td className="px-3 py-2 text-purple-700 dark:text-purple-300 text-right font-semibold">{formatNum(row.PSI_Contribution, 6)}</td>
                      </tr>
                    ))}
                    <tr className="bg-purple-50 dark:bg-slate-900/80 font-semibold">
                      <td colSpan={2} className="px-3 py-2 text-purple-900 dark:text-purple-200">TOTAL PSI</td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">
                        {monotonicity.psi_breakdown.reduce((sum, r) => sum + r.Expected_Count, 0).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">100.00%</td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">
                        {monotonicity.psi_breakdown.reduce((sum, r) => sum + r.Actual_Count, 0).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">100.00%</td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">-</td>
                      <td className="px-3 py-2 text-purple-900 dark:text-purple-200 text-right">
                        {formatNum(monotonicity.psi_breakdown.reduce((sum, r) => sum + r.PSI_Contribution, 0), 6)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="mt-3 text-xs text-purple-700 dark:text-purple-200 bg-purple-50 dark:bg-slate-900/60 p-2 rounded">
                <div className="font-semibold mb-1">Formula per bin:</div>
                <div className="font-mono text-[10px]">
                  PSI_Contribution = (Actual% - Expected%) × ln(Actual% / Expected%)
                </div>
                <div className="mt-1 text-purple-600 dark:text-purple-300">
                  Total PSI = Sum of all PSI Contributions = {formatNum(monotonicity.psi || 0, 6)}
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                <CheckCircle className={`h-4 w-4 ${monotonicity.monotonicity_pass ? 'text-emerald-500' : 'text-amber-500'}`} />
                Monotonicity Score
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
                {formatPct(monotonicity.monotonicity_score)}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {isMonotonic ? 'No violations detected' : `${violationsData.length} violation(s)`}
              </div>
            </div>

            <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                <LineChart className="h-4 w-4 text-blue-500" />
                KS Statistic
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{formatNum(monotonicity.ks, 3)}</div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Threshold {formatNum(monotonicity.ks_threshold, 3)} · Decile {formatNum(monotonicity.ks_decile, 1)}
              </div>
            </div>

            <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                <TrendingUp className="h-4 w-4 text-indigo-500" />
                Lift (Top Decile)
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{formatNum(monotonicity.lift_top_decile ?? null, 2)}x</div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Overall bad rate {formatPct(monotonicity.overall_bad_rate)}</div>
            </div>

            <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                <TrendingUp className="h-4 w-4 text-teal-500" />
                AUC / Gini
              </div>
              <div className="text-xl font-semibold text-gray-900 dark:text-white mt-2">
                AUC {formatNum(monotonicity.auc, 3)} · Gini {formatNum(monotonicity.gini, 3)}
              </div>
            </div>
          </div>

          {violationsData.length > 0 && (
            <div className="border border-amber-200 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 rounded-lg p-3 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5" />
              <div className="text-sm">
                <div className="font-semibold">Monotonicity violations</div>
                <ul className="list-disc list-inside">
                  {violationsData.map((v: Record<string, unknown>, idx: number) => (
                    <li key={`${v.from_decile}-${v.to_decile}-${idx}`}>
                      {isAdvancedMonotonicity 
                        ? `Decile ${v.from_decile} → ${v.to_decile}: drop ${formatPct(v.drop as number)}`
                        : `Segment ${v.segment_from} → ${v.segment_to}: drop ${formatPct(v.drop as number)}`
                      }
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {monotonicitySummaryLines.length > 0 && (
            <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 text-sm text-gray-800 dark:text-gray-200 space-y-1 bg-gray-50 dark:bg-slate-900/60">
              <div className="font-semibold text-gray-900 dark:text-white">Decile progression</div>
              {monotonicitySummaryLines.map((line, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="text-gray-600 dark:text-gray-300 tabular-nums">{line}</span>
                </div>
              ))}
              {violationsData.length === 0 && (
                <div className="pt-2 text-emerald-700 dark:text-emerald-300 font-semibold">
                  ✓ PERFECT MONOTONICITY - No violations detected.
                </div>
              )}
            </div>
          )}

          {isAdvancedMonotonicity && decilesData.length > 0 && (
            <div className="border border-gray-200 dark:border-slate-700 rounded-lg overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 dark:bg-slate-900">
                <tr>
                  {['Decile', 'Count', 'Bads', 'Goods', 'Bad Rate', 'Avg Score', 'Lift', 'Cum Bad Rate'].map((col) => (
                    <th key={col} className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-800 bg-white dark:bg-slate-900/60">
                {decilesData.map((row: DecileRow, idx: number) => (
                  <tr
                    key={idx}
                    className={`hover:bg-gray-50 dark:hover:bg-slate-800 dark:hover:bg-slate-800 ${violationDeciles.has(row.Decile) ? 'bg-amber-50 dark:bg-amber-900/20' : ''}`}
                  >
                    <td className="px-4 py-2 text-gray-900 dark:text-gray-200 font-medium">{row.Decile}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{row.Count}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{row.Bads}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{row.Goods}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{formatPct(row.Bad_Rate)}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{formatNum(row.Avg_Score, 3)}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{formatNum(row.Lift, 2)}x</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{formatPct(row.Cum_Bad_Rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}

        {isSimpleMonotonicity && (
          <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-6 bg-white dark:bg-slate-900/60">
            <h5 className="font-semibold text-gray-900 dark:text-white mb-4">Segment Monotonicity Analysis</h5>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                <div className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Monotonicity Score</div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{formatPct(monotonicityScore)}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {isMonotonic ? 'Perfect monotonicity' : `${violationsData.length} violation(s)`}
                </div>
              </div>
              <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                <div className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Total Segments</div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{(monotonicity as any).total_segments || 0}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Segments analyzed</div>
              </div>
            </div>
          </div>
        )}

          {isAdvancedMonotonicity && violationsData.length > 0 && (
            <div className="text-xs text-gray-600 dark:text-gray-400">
              Rows highlighted in amber mark deciles where the bad rate decreased vs the prior decile.
            </div>
          )}
        </>
      )}

      {/* PSI & CSI Modal */}
      <PSICSIModal
        isOpen={isPSICSIModalOpen}
        onClose={() => setIsPSICSIModalOpen(false)}
        monotonicity={monotonicity}
      />
    </div>
  );
};

export default MonotonicityTab;
