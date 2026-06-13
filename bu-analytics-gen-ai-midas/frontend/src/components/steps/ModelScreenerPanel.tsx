import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Filter, Sparkles, Zap } from 'lucide-react';
import {
  collectResultsToProcess,
  computeFilteredModelsFromPool,
  filterOperators,
  fingerprintMtaTrainingResults,
  getAvailableMetricsForScreener,
  getManualScreenerDisplayMetrics,
  getManualScreenerModelKey,
  getMetricDisplayName,
  resolveNonzeroFeatureCount,
  resolveTrainingBundleUsedFeatures,
  readPrunedScreenerQueue,
  clearMtaScreenerSelectedKeys,
  writeMtaScreenerPhaseDone,
  writeMtaScreenerSelectedKeys,
  type ModelFilterRow,
} from './modelScreenerUtils';
import { MTA_THEAD } from './modelTrainingMtaUi';

const MAX_SLOTS = 4;
const TABLE_PREVIEW_ROWS = 18;

function getFirstFiniteMetric(metricObj: any, keys: string[]): number | null {
  if (!metricObj || typeof metricObj !== 'object') return null;
  for (const key of keys) {
    const raw = metricObj[key];
    if (raw === null || raw === undefined) continue;
    if (typeof raw === 'string' && raw.trim() === '') continue;
    const val = typeof raw === 'number' ? raw : Number(raw);
    if (Number.isFinite(val)) return val;
  }
  return null;
}

function calcOverfitPct(trainVal: number | null, testVal: number | null): number | null {
  if (trainVal === null || testVal === null || trainVal === 0) return null;
  return ((trainVal - testVal) / Math.abs(trainVal)) * 100.0;
}

function formatNum(value: any, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'N/A';
}

function formatNonZeroRatio(nonZero: number | null, total: number | null): string {
  if (nonZero !== null && total !== null && total > 0) return `${Math.round(nonZero)}/${Math.round(total)}`;
  if (nonZero !== null) return `${Math.round(nonZero)}`;
  return 'N/A';
}

function algorithmIcon(algorithm: string) {
  const a = algorithm.toLowerCase();
  if (a.includes('xgboost') || a === 'xgb') {
    return <Zap className="h-4 w-4 text-orange-500 shrink-0" aria-hidden />;
  }
  if (a.includes('light') || a === 'lgbm') {
    return <Sparkles className="h-4 w-4 text-rose-500 shrink-0" aria-hidden />;
  }
  if (a.includes('logistic') || a === 'lr') {
    return <span className="text-indigo-600 font-bold text-xs shrink-0 w-4 text-center">LR</span>;
  }
  return <span className="h-4 w-4 rounded-full bg-gray-300 dark:bg-gray-600 shrink-0" aria-hidden />;
}

type Props = {
  activeDatasetId?: string | null;
  /** When true, user has confirmed the screener and pruning is available below. */
  pruningPhaseUnlocked?: boolean;
  /**
   * Training snapshot aligned with Step 6 (live state + sessionStorage). Parent recomputes on
   * persist events so tab / reload stays in sync with Training insights.
   */
  trainingBundle: any | null;
};

const ModelScreenerPanel: React.FC<Props> = ({ activeDatasetId, pruningPhaseUnlocked = false, trainingBundle }) => {
  const trainingResults = trainingBundle;
  const [modelFilters, setModelFilters] = useState<ModelFilterRow[]>([]);
  const [selectedAlgorithmFilter, setSelectedAlgorithmFilter] = useState('');
  const [segmentFilter, setSegmentFilter] = useState('all');
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});
  const selectionSeededRef = useRef(false);
  const skipNextPersistRef = useRef(false);
  const [prunedQueueBump, setPrunedQueueBump] = useState(0);

  const resultsFingerprint = useMemo(() => fingerprintMtaTrainingResults(trainingResults), [trainingResults]);

  useEffect(() => {
    if (!resultsFingerprint) return;
    selectionSeededRef.current = false;
    setSelectedKeys({});
    clearMtaScreenerSelectedKeys(activeDatasetId ?? null);
    skipNextPersistRef.current = true;
  }, [resultsFingerprint, activeDatasetId]);

  useEffect(() => {
    if (!resultsFingerprint) return;
    if (skipNextPersistRef.current) {
      skipNextPersistRef.current = false;
      return;
    }
    const keys = Object.entries(selectedKeys)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (keys.length === 0 && !selectionSeededRef.current) return;
    writeMtaScreenerSelectedKeys(activeDatasetId ?? null, resultsFingerprint, keys);
    window.dispatchEvent(new Event('midas-mta-screener-selection-changed'));
  }, [selectedKeys, resultsFingerprint, activeDatasetId]);

  useEffect(() => {
    const onPruned = () => setPrunedQueueBump((b) => b + 1);
    window.addEventListener('midas-pruned-screener-queue-changed', onPruned);
    return () => window.removeEventListener('midas-pruned-screener-queue-changed', onPruned);
  }, []);

  const problemType = trainingResults?.problem_type || 'classification';

  const basePool = useMemo(() => {
    const fromTrain = collectResultsToProcess(trainingResults, segmentFilter);
    const extras = readPrunedScreenerQueue(activeDatasetId ?? null).filter(
      (e: any) => segmentFilter === 'all' || String(e?.segment_id ?? '') === String(segmentFilter),
    );
    return [...fromTrain, ...extras];
  }, [trainingResults, segmentFilter, activeDatasetId, prunedQueueBump]);

  const filtered = useMemo(
    () => computeFilteredModelsFromPool(basePool, problemType, modelFilters, selectedAlgorithmFilter),
    [basePool, problemType, modelFilters, selectedAlgorithmFilter],
  );

  const tableSource = useMemo(() => {
    if (!trainingResults) return [];
    if (!selectedAlgorithmFilter && modelFilters.length === 0) return basePool;
    return filtered;
  }, [trainingResults, basePool, filtered, selectedAlgorithmFilter, modelFilters.length]);

  const combinedPassCount = useMemo(() => {
    if (!modelFilters.length) return tableSource.length;
    return computeFilteredModelsFromPool(basePool, problemType, modelFilters, selectedAlgorithmFilter).length;
  }, [basePool, problemType, modelFilters, selectedAlgorithmFilter, tableSource.length]);

  const passCountForFilter = useCallback(
    (f: ModelFilterRow) =>
      computeFilteredModelsFromPool(basePool, problemType, [f], selectedAlgorithmFilter).length,
    [basePool, problemType, selectedAlgorithmFilter],
  );

  useEffect(() => {
    if (!trainingResults?.results?.length && !trainingResults?.segment_results) return;
    if (selectionSeededRef.current) return;

    const pool = collectResultsToProcess(trainingResults, 'all');
    const rowWithScores = pool
      .map((row: any) => {
        const metrics = getManualScreenerDisplayMetrics(row, problemType);
        const aucTe = getFirstFiniteMetric(metrics, ['test_auc', 'auc_test', 'auc']);
        const aucSort = typeof aucTe === 'number' && Number.isFinite(aucTe) ? aucTe : -Infinity;
        return { row, aucTe: aucSort };
      })
      .sort((a, b) => b.aucTe - a.aucTe);

    const perAlgorithmSelected: Record<string, boolean> = {};
    const selected: Record<string, boolean> = {};

    rowWithScores.forEach(({ row }) => {
      const algo = String(row?.algorithm || '').toLowerCase();
      const key = getManualScreenerModelKey(row);
      if (!algo || perAlgorithmSelected[algo]) return;
      if (Object.keys(selected).length >= MAX_SLOTS) return;
      perAlgorithmSelected[algo] = true;
      selected[key] = true;
    });

    if (Object.keys(selected).length > 0) {
      setSelectedKeys(selected);
    }
    selectionSeededRef.current = true;
  }, [trainingResults, problemType]);

  const rowsForTable = useMemo(() => {
    return tableSource
      .map((model: any) => {
        const displayMetrics = getManualScreenerDisplayMetrics(model, problemType);
        const aucTr = getFirstFiniteMetric(displayMetrics, ['train_auc', 'auc_train', 'auc']);
        const aucTe = getFirstFiniteMetric(displayMetrics, ['test_auc', 'auc_test', 'auc']);
        const ksTr = getFirstFiniteMetric(displayMetrics, ['train_ks_statistic', 'ks_train']);
        const ksTe = getFirstFiniteMetric(displayMetrics, ['test_ks_statistic', 'ks_test', 'ks_statistic']);
        const giniTr = getFirstFiniteMetric(displayMetrics, ['train_gini']) ?? (aucTr !== null ? 2 * aucTr - 1 : null);
        const giniTe = getFirstFiniteMetric(displayMetrics, ['test_gini']) ?? (aucTe !== null ? 2 * aucTe - 1 : null);
        const overfit = getFirstFiniteMetric(displayMetrics, ['overfit_pct']) ?? calcOverfitPct(aucTr, aucTe);
        const bundleUF = resolveTrainingBundleUsedFeatures(trainingResults, model?.segment_id);
        const totalFeat =
          getFirstFiniteMetric(displayMetrics, ['feature_count']) ??
          (Array.isArray(model?.used_features) ? model.used_features.length : null) ??
          (Array.isArray(bundleUF) ? bundleUF.length : null);
        const nzFeat = resolveNonzeroFeatureCount(model, displayMetrics, bundleUF);
        const nonZeroLabel = formatNonZeroRatio(nzFeat, totalFeat);
        const guideline = model?.guideline || 'G1';
        return {
          key: getManualScreenerModelKey(model),
          raw: model,
          algorithm: String(model?.algorithm || ''),
          guideline,
          aucTr,
          aucTe,
          ksTr,
          ksTe,
          giniTr,
          giniTe,
          overfit,
          nonZeroLabel,
        };
      })
      .sort((a, b) => {
        const left = typeof a.aucTe === 'number' && Number.isFinite(a.aucTe) ? a.aucTe : -Infinity;
        const right = typeof b.aucTe === 'number' && Number.isFinite(b.aucTe) ? b.aucTe : -Infinity;
        return right - left;
      });
  }, [tableSource, problemType, trainingBundle]);

  const { orderedRows, selectedCount, remainderSlots } = useMemo(() => {
    const selectedRows = rowsForTable.filter((r) => selectedKeys[r.key]);
    const otherRows = rowsForTable.filter((r) => !selectedKeys[r.key]);
    const cnt = selectedRows.length;
    return {
      orderedRows: [...selectedRows, ...otherRows],
      selectedCount: cnt,
      remainderSlots: Math.max(0, MAX_SLOTS - cnt),
    };
  }, [rowsForTable, selectedKeys]);

  const algorithmOptions = useMemo(() => {
    const set = new Set<string>();
    basePool.forEach((m: any) => {
      if (m.algorithm) set.add(m.algorithm);
    });
    return Array.from(set);
  }, [basePool]);

  if (!trainingResults || (!trainingResults.results?.length && !trainingResults.segment_results)) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-slate-900/50 p-8 text-center">
        <Filter className="h-10 w-10 mx-auto mb-3 text-gray-400" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Model screener</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-lg mx-auto">
          Run model training on this page first. When results are available, candidates appear here for filtering and
          shortlist selection (up to {MAX_SLOTS} models).
        </p>
      </div>
    );
  }

  return (
    <div id="model-screener" className="space-y-4 mb-8 scroll-mt-28">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white tracking-tight">Model screener</h3>
        
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex flex-wrap items-start justify-between gap-3 bg-gray-50 dark:bg-slate-900">
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white">Candidate model selection</h4>
            
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200 dark:bg-slate-800 dark:text-gray-200 dark:border-gray-600">
              {selectedCount} of {MAX_SLOTS} slots
            </span>
          </div>
        </div>

        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-gray-900">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Algorithm</label>
            <select
              value={selectedAlgorithmFilter}
              onChange={(e) => setSelectedAlgorithmFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All ({algorithmOptions.length})</option>
              {algorithmOptions.map((alg) => (
                <option key={alg} value={alg}>
                  {alg}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end justify-end">
            <span className="text-xs text-gray-500 dark:text-gray-400">{rowsForTable.length} models in table</span>
          </div>
        </div>

        {trainingResults.segment_results && (
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-blue-50/40 dark:bg-slate-800/40">
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Segment</label>
            <select
              value={segmentFilter}
              onChange={(e) => setSegmentFilter(e.target.value)}
              className="w-full max-w-md px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All segments</option>
              {(trainingResults.segments || []).map((s: string) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50/90 dark:bg-slate-900/80">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Filters (AND logic)
            </span>
            <button
              type="button"
              onClick={() => {
                const pt = problemType;
                setModelFilters((prev) => [
                  ...prev,
                  { metric: pt === 'classification' ? 'test_auc' : 'test_r2', operator: '>=', value: '0.5' },
                ]);
              }}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 dark:bg-[#292966] dark:text-[#ccccff] dark:hover:bg-[#333380] shadow-sm"
            >
              + Add filter
            </button>
          </div>

          {modelFilters.map((filter, index) => (
            <div
              key={`${filter.metric}_${index}`}
              className="grid grid-cols-1 md:grid-cols-[1.2fr_0.7fr_0.8fr_auto_auto] gap-2 mb-2 items-end"
            >
              <div>
                <label className="block text-[10px] font-medium text-gray-500 mb-0.5">Metric</label>
                <select
                  value={filter.metric}
                  onChange={(e) => {
                    const next = [...modelFilters];
                    next[index] = { ...next[index], metric: e.target.value };
                    setModelFilters(next);
                  }}
                  className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-xs bg-white dark:bg-gray-900 dark:text-white"
                >
                  {getAvailableMetricsForScreener(trainingResults).map((m) => (
                    <option key={m} value={m}>
                      {getMetricDisplayName(m)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-medium text-gray-500 mb-0.5">Op</label>
                <select
                  value={filter.operator}
                  onChange={(e) => {
                    const next = [...modelFilters];
                    next[index] = { ...next[index], operator: e.target.value as ModelFilterRow['operator'] };
                    setModelFilters(next);
                  }}
                  className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-xs bg-white dark:bg-gray-900 dark:text-white"
                >
                  {filterOperators.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-medium text-gray-500 mb-0.5">Value</label>
                <input
                  type="number"
                  step="0.001"
                  value={filter.value}
                  onChange={(e) => {
                    const next = [...modelFilters];
                    next[index] = { ...next[index], value: e.target.value };
                    setModelFilters(next);
                  }}
                  className="w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-xs bg-white dark:bg-gray-900 dark:text-white"
                />
              </div>
              <span className="text-[11px] text-emerald-700 dark:text-emerald-400 font-medium whitespace-nowrap pb-1">
                {passCountForFilter(filter)} pass
              </span>
              <button
                type="button"
                title="Remove filter"
                onClick={() => setModelFilters(modelFilters.filter((_, i) => i !== index))}
                className="text-red-600 hover:text-red-800 text-lg leading-none pb-1 px-1"
              >
                ×
              </button>
            </div>
          ))}

          {modelFilters.length === 0 && (
            <p className="text-xs text-gray-500 dark:text-gray-400 py-2">No filters — all models in the table below.</p>
          )}

          <div className="flex justify-end mt-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Combined: <span className="font-semibold text-gray-900 dark:text-white">{combinedPassCount}</span> models pass
            </span>
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="w-full min-w-[1040px] text-xs">
            <thead className={MTA_THEAD}>
              <tr>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px] w-12">SEL</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">Algorithm</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">Guide</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">AUC (TR)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">AUC (TE)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">KS (TR)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">KS (TE)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">GINI (TR)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">GINI (TE)</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">Overfit</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">Feat.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
              {orderedRows.slice(0, TABLE_PREVIEW_ROWS).map((row, idx) => {
                const isSelected = !!selectedKeys[row.key];
                const showSeparatorBand =
                  selectedCount > 0 &&
                  idx === selectedCount &&
                  selectedCount < orderedRows.length;

                return (
                  <React.Fragment key={row.key}>
                    {showSeparatorBand ? (
                      <tr className="bg-gray-100 dark:bg-slate-800/80">
                        <td colSpan={11} className="px-3 py-2 text-[11px] font-medium text-gray-600 dark:text-gray-300">
                          Other candidates ({remainderSlots} slot{remainderSlots === 1 ? '' : 's'} remaining)
                        </td>
                      </tr>
                    ) : null}
                    <tr
                      className={
                        isSelected
                          ? 'bg-blue-50/90 dark:bg-blue-950/25 hover:bg-blue-50 dark:hover:bg-blue-950/35'
                          : 'bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-slate-800/70'
                      }
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setSelectedKeys((prev) => {
                              const next = { ...prev };
                              if (checked) {
                                const n = Object.values(prev).filter(Boolean).length;
                                if (n >= MAX_SLOTS) {
                                  window.alert(`You can select up to ${MAX_SLOTS} models only.`);
                                  return prev;
                                }
                                next[row.key] = true;
                              } else {
                                delete next[row.key];
                              }
                              return next;
                            });
                          }}
                          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                        />
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <div className="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
                          {algorithmIcon(row.algorithm)}
                          <span>{row.algorithm || '—'}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            row.guideline === 'G1'
                              ? 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-200 dark:border-emerald-800'
                              : 'bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-800'
                          }`}
                        >
                          {row.guideline}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.aucTr, 3)}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.aucTe, 3)}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.ksTr, 3)}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.ksTe, 3)}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.giniTr, 3)}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatNum(row.giniTe, 3)}</td>
                      <td
                        className={`px-3 py-2 whitespace-nowrap font-medium ${
                          row.overfit !== null && row.overfit <= 10
                            ? 'text-emerald-700 dark:text-emerald-400'
                            : 'text-amber-700 dark:text-amber-300'
                        }`}
                      >
                        {row.overfit !== null && Number.isFinite(row.overfit) ? `${Number(row.overfit).toFixed(2)}%` : 'N/A'}
                      </td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.nonZeroLabel}</td>
                    </tr>
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {orderedRows.length > TABLE_PREVIEW_ROWS && (
          <div className="px-4 py-2 text-center text-[11px] text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
            … {orderedRows.length - TABLE_PREVIEW_ROWS} more models (scroll table horizontally; extend rows in a future update) …
          </div>
        )}

        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-900/80 space-y-3">
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:justify-between">
            
            {pruningPhaseUnlocked ? (
              <p className="text-xs font-medium text-emerald-800 dark:text-emerald-200 shrink-0">
                Shortlist confirmed — model pruning is unlocked below.
              </p>
            ) : (
              <button
                type="button"
                disabled={selectedCount < 1}
                onClick={() => {
                  const fp = fingerprintMtaTrainingResults(trainingResults);
                  writeMtaScreenerPhaseDone(activeDatasetId ?? null, fp);
                  window.dispatchEvent(new Event('midas-mta-screener-phase-complete'));
                }}
                className="w-full sm:w-auto px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 dark:bg-[#292966] dark:text-[#ccccff] dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
              >
                Confirm shortlist &amp; unlock pruning
              </button>
            )}
          </div>
          {!pruningPhaseUnlocked && selectedCount < 1 && (
            <p className="text-[11px] text-amber-800 dark:text-amber-200">
              Select at least one model in the table, then confirm to continue to pruning.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ModelScreenerPanel;
