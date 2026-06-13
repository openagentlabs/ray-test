/**
 * Step 3 - Iterative Feature Elimination (XGBoost-SHAP RFE).
 *
 * Consumes Step 2 output (locked + screened variables + pre-computed metrics),
 * starts the backend RFE job, streams live iteration ticks via SSE, and renders
 * the wireframe's 5-tile summary / adaptive-elimination strip / features bar
 * chart / iteration log / completion banner stack.
 *
 * Data rule: always runs on the whole training partition (enforced server-side;
 * the UI does not need to thread any segment_id).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  CheckCircle,
  Loader,
  Settings,
  StopCircle,
} from 'lucide-react';

import { MTA_THEAD } from '../modelTrainingMtaUi';

import {
  cancelRfe,
  getRfeResult,
  getRfeStatus,
  RfeIterationRecord,
  RfeResultResponse,
  RfeStatusResponse,
  startRfe,
  streamRfe,
  type RfeSseEvent,
  type RfeStartRequest,
} from '../../../services/rfeService';
import { fmt, getRfeTheme, RFE_AMBER, RFE_BLUE, RFE_GREEN, RFE_RED } from './shared';

export interface RFEStepProps {
  startPayload: RfeStartRequest | null;
  isDarkMode: boolean;
  activeJobId?: string | null;
  /**
   * Optional result to seed the component when the RFE has already finished in
   * a previous session (restored from sessionStorage). Prevents the UI from
   * flashing "pending" while SSE replays historical iterations on remount.
   */
  initialResult?: RfeResultResponse | null;
  /**
   * When true, the step is locked (user has already finalized in Step 4).
   * Hides cancel / continue-to-review / back actions. The table and chart
   * stay visible so the user can inspect what was run.
   */
  readOnly?: boolean;
  /**
   * Count of locked variables (Step 1 decisions). Used by the Starting
   * Features / Final Features tiles for the "X locked + Y retained/screened"
   * subscript. Parent derives these from startPayload.working_set.
   */
  lockedCount: number;
  /**
   * Count of screened-in variables (Step 2 survivors, excluding locked).
   * Used by the Starting Features tile subscript.
   */
  screenedCount: number;
  onJobIdAssigned?: (jobId: string) => void;
  onCompleted: (result: RfeResultResponse) => void;
  onBack?: () => void;
}

// Small helper: capitalize a backend status string for display ("running" ->
// "Running"). Never returns a raw lowercase value to the UI.
const toTitle = (s?: string | null): string =>
  s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : '—';

const RFEStep: React.FC<RFEStepProps> = ({
  startPayload,
  isDarkMode,
  activeJobId,
  initialResult,
  readOnly,
  lockedCount,
  screenedCount,
  onJobIdAssigned,
  onCompleted,
  onBack: _onBack,
}) => {
  const theme = getRfeTheme(isDarkMode);

  const [jobId, setJobId] = useState<string | null>(activeJobId ?? null);
  const [status, setStatus] = useState<RfeStatusResponse | null>(null);
  const [iterations, setIterations] = useState<RfeIterationRecord[]>(
    initialResult?.iterations ?? []
  );
  const [result, setResult] = useState<RfeResultResponse | null>(initialResult ?? null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<boolean>(false);
  const [cancelling, setCancelling] = useState<boolean>(false);
  const streamRef = useRef<{ close: () => void } | null>(null);
  // Guard against React 18 StrictMode double-invocation of effects in dev,
  // which otherwise POSTs /rfe/start twice and spawns two daemon threads that
  // fight over the joblib/loky subprocess pool.
  const startedRef = useRef<boolean>(false);

  // Keep callback props in refs so the SSE/polling effects below don't need
  // to list them in their dependency arrays. The parent component re-renders
  // frequently and passes fresh inline arrows on every render; without this
  // indirection the effects would tear down the SSE connection and clear the
  // polling interval on every parent re-render, starving the UI of updates.
  const onCompletedRef = useRef(onCompleted);
  const onJobIdAssignedRef = useRef(onJobIdAssigned);
  useEffect(() => {
    onCompletedRef.current = onCompleted;
  }, [onCompleted]);
  useEffect(() => {
    onJobIdAssignedRef.current = onJobIdAssigned;
  }, [onJobIdAssigned]);

  // --------------------- start (or reuse existing job) ---------------------
  useEffect(() => {
    if (jobId) return; // already started
    if (!startPayload) return;
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      try {
        setStarting(true);
        const resp = await startRfe(startPayload);
        setJobId(resp.job_id);
        onJobIdAssignedRef.current?.(resp.job_id);
      } catch (err) {
        startedRef.current = false;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setStarting(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startPayload]);

  // --------------------- SSE ---------------------
  useEffect(() => {
    if (!jobId) return;
    const handle = streamRfe(
      jobId,
      {
        onEvent: (ev: RfeSseEvent) => {
          if (ev.kind === 'status') {
            setStatus(ev.payload);
          }
          if (ev.kind === 'iteration') {
            setIterations((prev) => {
              const next = prev.slice();
              const idx = next.findIndex((it) => it.iteration === ev.iteration.iteration);
              if (idx >= 0) next[idx] = ev.iteration;
              else next.push(ev.iteration);
              next.sort((a, b) => a.iteration - b.iteration);
              return next;
            });
          }
          if (ev.kind === 'final') {
            const hasFullResult =
              !!ev.result && Array.isArray(ev.result.rows) && Array.isArray(ev.result.iterations);
            if (hasFullResult && ev.result) {
              setResult(ev.result);
              setIterations(ev.result.iterations);
              onCompletedRef.current(ev.result);
            } else {
              (async () => {
                try {
                  const r = await getRfeResult(jobId);
                  setResult(r);
                  setIterations(r.iterations);
                  onCompletedRef.current(r);
                } catch (err) {
                  setError(err instanceof Error ? err.message : String(err));
                }
              })();
            }
          }
          if (ev.kind === 'error') {
            setError(ev.error);
          }
        },
        onError: (err) => {
          setError(err.message);
        },
      },
      { maxReconnects: 4, reconnectDelayMs: 1500 }
    );
    streamRef.current = handle;
    return () => {
      try {
        handle.close();
      } catch {
        /* ignore */
      }
      streamRef.current = null;
    };
  }, [jobId]);

  // --------------------- polling fallback ---------------------
  useEffect(() => {
    if (!jobId || result) return;
    const interval = setInterval(async () => {
      try {
        const s = await getRfeStatus(jobId);
        setStatus(s);
        if (s.status === 'completed' && !result) {
          const r = await getRfeResult(jobId);
          setResult(r);
          setIterations(r.iterations);
          onCompletedRef.current(r);
        }
        if (s.status === 'failed' || s.status === 'cancelled') {
          if (s.error) setError(s.error);
        }
      } catch {
        /* transient; ignore */
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [jobId, result]);

  // --------------------- derived ---------------------

  const bestIter = useMemo<RfeIterationRecord | null>(
    () =>
      iterations.reduce<RfeIterationRecord | null>(
        (best, it) => (!best || it.cv_auc > best.cv_auc ? it : best),
        null
      ),
    [iterations]
  );

  // Per-iteration bar color: neutral gray for the baseline, green for the best
  // iteration, red when CV AUC dropped by more than 5% vs previous, amber for
  // a negative-but-small drop, blue otherwise. Cell expects a plain HEX color.
  const barColorFor = (it: RfeIterationRecord): string => {
    if (it.iteration === 0) return isDarkMode ? '#6b7280' : '#9ca3af';
    if (bestIter && it.iteration === bestIter.iteration) return RFE_GREEN;
    const d = it.relative_delta_from_prev;
    if (typeof d === 'number') {
      if (d < -0.05) return RFE_RED;
      if (d < 0) return RFE_AMBER;
    }
    return RFE_BLUE;
  };

  const chartData = useMemo(
    () =>
      iterations.map((it) => ({
        iter: it.iteration === 0 ? '0 (Base)' : `#${it.iteration}`,
        features: it.feature_count,
        color: barColorFor(it),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [iterations, bestIter, isDarkMode]
  );

  const latest = iterations.length > 0 ? iterations[iterations.length - 1] : null;
  const iter0 = iterations.find((it) => it.iteration === 0) ?? null;
  const isTerminal = status
    ? ['completed', 'failed', 'cancelled'].includes(status.status)
    : !!result;

  // Surface-level values used by tiles. Guard each value against NaN so the
  // "NaN of 10 so far" bug can't resurface on an empty iterations array.
  const startingFeatures = (lockedCount || 0) + (screenedCount || 0);
  const finalFeatureCount = result?.final_feature_count ?? latest?.feature_count ?? startingFeatures;
  const retainedCount = Math.max(0, finalFeatureCount - (lockedCount || 0));
  const displayStatus = toTitle(
    status?.status ??
      (starting ? 'starting' : result ? 'completed' : jobId ? 'connecting' : 'pending')
  );

  const handleCancel = async () => {
    if (!jobId) return;
    setCancelling(true);
    try {
      await cancelRfe(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCancelling(false);
    }
  };

  // --------------------- render ---------------------
  return (
    <div className="space-y-4">
      {/* Summary metrics — 5 tiles per wireframe */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        <SummaryTile theme={theme} label="STATUS" value={displayStatus} />
        <SummaryTile
          theme={theme}
          label="STARTING FEATURES"
          value={startingFeatures}
          sub={`${lockedCount} locked + ${screenedCount} screened`}
        />
        <SummaryTile
          theme={theme}
          label="FINAL FEATURES"
          value={result || latest ? finalFeatureCount : '—'}
          sub={`${lockedCount} locked + ${retainedCount} retained`}
        />
        <SummaryTile
          theme={theme}
          label="ITERATIONS"
          value={iterations.length}
          sub={bestIter ? `Best at iteration ${bestIter.iteration}` : '—'}
        />
        <SummaryTile
          theme={theme}
          label="BEST CV AUC"
          value={fmt(bestIter?.cv_auc ?? status?.latest_cv_auc ?? null)}
          sub={bestIter ? `Iteration ${bestIter.iteration}` : '—'}
        />
      </div>

      {/* Adaptive elimination policy strip */}
      <div
        className={`rounded-lg border px-3 py-2 text-xs flex items-start ${
          isDarkMode
            ? 'bg-slate-800/60 border-slate-700 text-gray-200'
            : 'bg-white border-gray-200 text-gray-800'
        }`}
      >
        <Settings className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" style={{ color: theme.accent }} />
        <div className="leading-5">
          <span className="font-semibold mr-1">Adaptive elimination:</span>
          100+ feat → bottom 5% | 50-100 → 3% | 25-49 → 2% | &lt;25 → 1%
          <span className="mx-3 opacity-40">•</span>
          <span className="font-semibold mr-1">Floor:</span>
          10% of starting set + locked count
          <span className="mx-3 opacity-40">•</span>
          <span className="font-semibold mr-1">Constraints:</span>
          locked vars never dropped
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-700 p-3 text-xs text-red-800 dark:text-red-200 flex items-start">
          <AlertTriangle className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {/* Features-per-iteration bar chart (single series, semantic colors).
          NOTE: recharts caches bar geometry on first paint when
          `isAnimationActive={false}`, which meant the chart only filled in
          at the end of the run instead of growing bar-by-bar as SSE
          iteration events arrived. We keep animation ON (short duration so
          it still "pops in" per iteration) and key the chart by the current
          iteration count so recharts re-lays out whenever a new iteration
          is appended to `chartData`. */}
      <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} p-3`}>
        <div className={`text-sm font-semibold ${theme.textStrong} mb-2`}>Features per iteration</div>
        <div className="w-full h-[220px] min-h-[220px] min-w-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} debounce={50}>
            <BarChart
              key={`rfe-chart-${chartData.length}-${isDarkMode}`}
              data={chartData}
              margin={{ top: 18, right: 12, bottom: 4, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={theme.gridLine} />
              <XAxis dataKey="iter" tick={{ fontSize: 11, fill: isDarkMode ? '#cbd5e1' : '#475569' }} />
              <YAxis tick={{ fontSize: 11, fill: isDarkMode ? '#cbd5e1' : '#475569' }} />
              <Bar
                dataKey="features"
                name="Features"
                isAnimationActive={true}
                animationDuration={250}
              >
                {chartData.map((d, i) => (
                  <Cell key={i} fill={d.color} />
                ))}
                <LabelList
                  dataKey="features"
                  position="top"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    fill: isDarkMode ? '#e2e8f0' : '#334155',
                  }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Iteration log table */}
      <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg}`}>
        <div className={`text-sm font-semibold ${theme.textStrong} px-3 py-2 border-b ${theme.panelBorder}`}>
          Iteration log
        </div>
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className={`${MTA_THEAD} sticky top-0 z-10`}>
              <tr>
                <th className="px-3 py-2 text-left font-semibold tracking-wider">ITERATION</th>
                <th className="px-3 py-2 text-right font-semibold tracking-wider">FEATURES</th>
                <th className="px-3 py-2 text-right font-semibold tracking-wider">DROP</th>
                <th className="px-3 py-2 text-left font-semibold tracking-wider">ELIMINATION RATE</th>
                <th className="px-3 py-2 text-right font-semibold tracking-wider">CV AUC</th>
                <th className="px-3 py-2 text-right font-semibold tracking-wider">TEST AUC</th>
                <th className="px-3 py-2 text-right font-semibold tracking-wider">Δ VS PREVIOUS</th>
                <th className="px-3 py-2 text-left font-semibold tracking-wider">STATUS</th>
              </tr>
            </thead>
            <tbody>
              {iterations.length === 0 && (
                <tr>
                  <td colSpan={8} className={`px-3 py-6 text-center ${theme.textMuted}`}>
                    {starting ? 'Starting job...' : 'Waiting for first iteration...'}
                  </td>
                </tr>
              )}
              {iterations.map((it) => (
                <IterationRow
                  key={it.iteration}
                  it={it}
                  isBest={bestIter?.iteration === it.iteration}
                  isDarkMode={isDarkMode}
                  theme={theme}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Completion banner (replaces old "Stop reason: ..." line) */}
      {result && iter0 && bestIter && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs flex items-start ${
            isDarkMode
              ? 'bg-green-900/20 border-green-700 text-green-100'
              : 'bg-green-50 border-green-300 text-green-900'
          }`}
        >
          <CheckCircle className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0 text-green-600 dark:text-green-300" />
          <div className="leading-5">
            <span className="font-semibold">RFE complete.</span>{' '}
            Optimal set at iteration {bestIter.iteration}: {result.final_feature_count} variables (
            {lockedCount} locked + {retainedCount} retained). CV AUC improved {fmt(iter0.cv_auc)} to{' '}
            {fmt(bestIter.cv_auc)} ({signedPct((bestIter.cv_auc - iter0.cv_auc) / Math.max(iter0.cv_auc, 1e-9))} relative),
            features reduced {result.starting_feature_count} to {result.final_feature_count} (
            {pctReduction(result.starting_feature_count, result.final_feature_count)}% reduction).
            {result.rolled_back_from_iteration != null && (
              <>
                {' '}
                <span className="font-semibold">
                  Rolled back from iteration {result.rolled_back_from_iteration}.
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Actions footer — minimal, only Cancel / Locked badge remain */}
      <div className="flex items-center justify-end">
        <div className="space-x-2">
          {readOnly ? (
            <span className="text-xs inline-flex items-center px-2 py-1 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-200">
              <CheckCircle className="w-3 h-3 mr-1" />
              Locked (feature selection finalized)
            </span>
          ) : (
            <>
              {!isTerminal && (
                <button
                  onClick={handleCancel}
                  disabled={!jobId || cancelling}
                  className="text-xs px-3 py-1.5 rounded border border-red-300 bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-200 disabled:opacity-50 inline-flex items-center"
                >
                  <StopCircle className="w-3 h-3 mr-1" />
                  {cancelling ? 'Cancelling...' : 'Cancel'}
                </button>
              )}
              {!jobId && starting && (
                <span className="text-xs inline-flex items-center" style={{ color: theme.accent }}>
                  <Loader className="w-3 h-3 mr-1 animate-spin" /> Starting...
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ---------------- helpers ----------------

const signedPct = (v: number): string => {
  if (!Number.isFinite(v)) return '—';
  const pct = v * 100;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
};

const pctReduction = (start: number, final: number): string => {
  if (!start || !Number.isFinite(start)) return '0';
  const pct = ((start - final) / start) * 100;
  return pct.toFixed(1);
};

interface IterationRowProps {
  it: RfeIterationRecord;
  isBest: boolean;
  isDarkMode: boolean;
  theme: ReturnType<typeof getRfeTheme>;
}

const IterationRow: React.FC<IterationRowProps> = ({ it, isBest, isDarkMode, theme }) => {
  const isBaseline = it.iteration === 0;
  const delta = it.relative_delta_from_prev;

  // Row background follows status priority:
  //   Stop (Δ < -5%) > Best > (default)
  let rowBg = '';
  if (!isBaseline && typeof delta === 'number' && delta < -0.05) {
    rowBg = isDarkMode ? 'bg-red-900/20' : 'bg-red-50';
  } else if (isBest && !isBaseline) {
    rowBg = isDarkMode ? 'bg-green-900/20' : 'bg-green-50';
  }

  // Elimination rate: prefer the backend's own band label so policy changes
  // never desync from the UI; fall back to "1 of N" when missing.
  const eliminationRate = isBaseline
    ? '—'
    : it.elimination_band_label && it.elimination_band_label !== '-'
    ? it.elimination_band_label
    : `${it.features_dropped.length} drop`;

  // Δ formatting + color. Any negative delta is shown in red (bold when it
  // crossed the −5% stop threshold); positive deltas stay green. The Status
  // column below still uses amber for "Degraded" (small negative) vs red for
  // "Stop" (breached −5% threshold) so the two signals remain distinguishable.
  let deltaStr = '—';
  let deltaColor = theme.textMuted;
  if (!isBaseline && typeof delta === 'number') {
    const pct = delta * 100;
    const sign = pct >= 0 ? '+' : '';
    deltaStr = `${sign}${pct.toFixed(2)}%`;
    if (delta < -0.05) deltaColor = 'text-red-600 dark:text-red-300 font-semibold';
    else if (delta < 0) deltaColor = 'text-red-600 dark:text-red-300';
    else deltaColor = 'text-green-600 dark:text-green-300';
  }

  // Status cell: dot + (Best / Stop / Degraded / Baseline / blank).
  let dotClass = 'bg-green-500';
  let statusText: React.ReactNode = '';
  let statusWeight = '';
  if (isBaseline && isBest) {
    dotClass = 'bg-green-500';
    statusText = 'Best (Baseline)';
    statusWeight = 'font-semibold text-green-600 dark:text-green-300';
  } else if (isBaseline) {
    dotClass = 'bg-green-500';
    statusText = 'Baseline';
  } else if (typeof delta === 'number' && delta < -0.05) {
    dotClass = 'bg-red-500';
    statusText = 'Stop';
    statusWeight = 'font-semibold';
  } else if (isBest) {
    dotClass = 'bg-green-500';
    statusText = 'Best';
    statusWeight = 'font-semibold';
  } else if (typeof delta === 'number' && delta < 0) {
    dotClass = 'bg-orange-500';
    statusText = 'Degraded';
  } // else: green dot, empty text — matches wireframe.

  return (
    <tr className={rowBg || (it.iteration % 2 === 0 ? theme.tableRow : theme.tableZebra)}>
      <td className={`px-3 py-2 ${theme.textStrong}`}>
        {isBaseline ? '0 (Base)' : `#${it.iteration}`}
      </td>
      <td className={`px-3 py-2 text-right ${theme.textStrong}`}>{it.feature_count}</td>
      <td className={`px-3 py-2 text-right ${theme.textMuted}`}>
        {isBaseline ? '—' : it.features_dropped.length}
      </td>
      <td className={`px-3 py-2 ${theme.textMuted}`}>{eliminationRate}</td>
      <td className={`px-3 py-2 text-right ${theme.textStrong}`}>{fmt(it.cv_auc)}</td>
      <td className={`px-3 py-2 text-right ${theme.textMuted}`}>{fmt(it.test_auc)}</td>
      <td className={`px-3 py-2 text-right ${deltaColor}`}>{deltaStr}</td>
      <td className={`px-3 py-2 ${theme.textStrong}`}>
        <span className={`inline-block w-2 h-2 rounded-full mr-1 align-middle ${dotClass}`} />
        <span className={statusWeight}>{statusText}</span>
      </td>
    </tr>
  );
};

interface SummaryTileProps {
  theme: ReturnType<typeof getRfeTheme>;
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ReactNode;
}

const SummaryTile: React.FC<SummaryTileProps> = ({ theme, label, value, sub, icon }) => (
  <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} p-3`}>
    <div className={`flex items-center text-[11px] uppercase tracking-wider ${theme.textMuted}`}>
      {icon && <span className="mr-1">{icon}</span>}
      <span>{label}</span>
    </div>
    <div className={`mt-1 text-base font-semibold ${theme.textStrong}`}>{value}</div>
    {sub && <div className={`text-[11px] ${theme.textMuted}`}>{sub}</div>}
  </div>
);

export default RFEStep;
