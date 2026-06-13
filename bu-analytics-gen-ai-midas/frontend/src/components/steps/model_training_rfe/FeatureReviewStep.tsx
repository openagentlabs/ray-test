/**
 * Step 4 - Feature Review & Override with two-phase flow:
 *   Phase 1 (select)   : Retained / Dropped / All tables. User toggles include.
 *   Phase 2 (monotone) : Per-variable monotone constraint configuration,
 *                        Export RFE log, and the real "Confirm N & continue"
 *                        button that POSTs /rfe/finalize.
 *
 * Read-only mode (job already finalized) disables all interactive controls
 * but still lets the user navigate between the two phases to review what was
 * submitted.
 */

import React, { useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, CheckCircle, Download, Loader, Lock } from 'lucide-react';

import {
  finalizeRfe,
  RfeFinalizeResponse,
  RfeResultResponse,
  RfeVariableRow,
} from '../../../services/rfeService';
import { fmt, getRfeTheme } from './shared';
import { MTA_THEAD } from '../modelTrainingMtaUi';
import { downloadRfeLogCsv } from './exportRfeLog';

export interface FeatureReviewStepProps {
  result: RfeResultResponse;
  isDarkMode: boolean;
  readOnly?: boolean;
  finalization?: RfeFinalizeResponse | null;
  onFinalized: (response: RfeFinalizeResponse) => void;
  onBack?: () => void;
  onEditOverrides?: () => void;
}

type MonotoneDir = -1 | 0 | 1;
type Phase = 'select' | 'monotone';

const FeatureReviewStep: React.FC<FeatureReviewStepProps> = ({
  result,
  isDarkMode,
  readOnly,
  finalization,
  onFinalized,
  onBack,
  onEditOverrides,
}) => {
  const theme = getRfeTheme(isDarkMode);

  const retainedInitial = useMemo(
    () => new Set(result.rows.filter((r) => r.status === 'retained').map((r) => r.variable)),
    [result.rows]
  );

  const [included, setIncluded] = useState<Set<string>>(retainedInitial);
  const [monotone, setMonotone] = useState<Record<string, MonotoneDir>>(() => {
    const out: Record<string, MonotoneDir> = {};
    for (const row of result.rows) {
      const suggestion = ((row.suggested_monotone ?? 0) as MonotoneDir) || 0;
      out[row.variable] = suggestion;
    }
    return out;
  });
  const [tab, setTab] = useState<'retained' | 'dropped' | 'all'>('retained');
  const [search, setSearch] = useState<string>('');
  const [phase, setPhase] = useState<Phase>('select');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const totalSelected = included.size;
  const lockedCount = result.rows.filter((r) => r.locked).length;
  const droppedCount = result.rows.filter((r) => r.status === 'dropped').length;
  const retainedCount = retainedInitial.size;
  const nVarHeader = `${result.final_feature_count}-VAR VIF`;

  // Ascending rank map for retained variables (1..retainedCount), using the
  // feature's last non-null rank in rank_trajectory as the sort key.
  const retainedRankMap = useMemo(() => {
    const retainedRows = result.rows.filter((r) => r.status === 'retained');
    const ranked = retainedRows.map((r) => {
      const traj = r.rank_trajectory || [];
      let lastRank: number | null = null;
      for (let i = traj.length - 1; i >= 0; i -= 1) {
        const v = traj[i];
        if (v !== null && v !== undefined) {
          lastRank = v;
          break;
        }
      }
      return { variable: r.variable, rank: lastRank ?? Number.POSITIVE_INFINITY };
    });
    ranked.sort((a, b) => (a.rank - b.rank) || a.variable.localeCompare(b.variable));
    const map = new Map<string, number>();
    ranked.forEach((r, idx) => map.set(r.variable, idx + 1));
    return map;
  }, [result.rows]);

  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    const filtered = result.rows.filter((r) => {
      if (tab === 'retained' && r.status !== 'retained') return false;
      if (tab === 'dropped' && r.status !== 'dropped') return false;
      if (term && !r.variable.toLowerCase().includes(term)) return false;
      return true;
    });
    filtered.sort((a, b) => {
      const aRet = a.status === 'retained';
      const bRet = b.status === 'retained';
      if (aRet !== bRet) return aRet ? -1 : 1;
      if (aRet && bRet) {
        const ka = retainedRankMap.get(a.variable) ?? Number.POSITIVE_INFINITY;
        const kb = retainedRankMap.get(b.variable) ?? Number.POSITIVE_INFINITY;
        if (ka !== kb) return ka - kb;
        return a.variable.localeCompare(b.variable);
      }
      const da = a.drop_iteration ?? Number.POSITIVE_INFINITY;
      const db = b.drop_iteration ?? Number.POSITIVE_INFINITY;
      if (da !== db) return da - db;
      return a.variable.localeCompare(b.variable);
    });
    return filtered;
  }, [result.rows, tab, search, retainedRankMap]);

  const toggleVariable = (row: RfeVariableRow) => {
    if (readOnly) return;
    setIncluded((prev) => {
      const next = new Set(prev);
      if (next.has(row.variable)) next.delete(row.variable);
      else next.add(row.variable);
      return next;
    });
  };

  const setMono = (variable: string, dir: MonotoneDir) => {
    setMonotone((prev) => ({ ...prev, [variable]: dir }));
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const retainedSet = retainedInitial;
      const overrideInclude: string[] = [];
      const overrideExclude: string[] = [];
      for (const row of result.rows) {
        const isIncluded = included.has(row.variable);
        const wasRetained = retainedSet.has(row.variable);
        if (isIncluded && !wasRetained) overrideInclude.push(row.variable);
        if (!isIncluded && wasRetained) overrideExclude.push(row.variable);
      }
      const mono: Record<string, MonotoneDir> = {};
      included.forEach((v) => {
        mono[v] = (monotone[v] ?? 0) as MonotoneDir;
      });
      const resp = await finalizeRfe({
        job_id: result.job_id,
        overrides: { include: overrideInclude, exclude: overrideExclude },
        monotone: mono,
      });
      onFinalized(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleExport = () => {
    try {
      downloadRfeLogCsv(result, included, monotone);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-4">
      {/* Summary tiles */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Tile theme={theme} label="Retained (RFE)" value={`${retainedCount}`} />
        <Tile theme={theme} label="Dropped" value={`${droppedCount}`} />
        <Tile theme={theme} label="Locked" value={`${lockedCount}`} />
        <Tile theme={theme} label="Selected" value={`${totalSelected}`} accent />
      </div>

      {phase === 'select' && (
        <SelectionPane
          theme={theme}
          tab={tab}
          setTab={setTab}
          search={search}
          setSearch={setSearch}
          visibleRows={visibleRows}
          retainedRankMap={retainedRankMap}
          retainedCount={retainedCount}
          droppedCount={droppedCount}
          totalRows={result.rows.length}
          nVarHeader={nVarHeader}
          included={included}
          toggleVariable={toggleVariable}
          readOnly={!!readOnly}
        />
      )}

      {phase === 'monotone' && (
        <MonotoneConfigPane
          theme={theme}
          rows={result.rows}
          included={included}
          setIncluded={setIncluded}
          monotone={monotone}
          setMono={setMono}
          readOnly={!!readOnly}
        />
      )}

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-700 p-3 text-xs text-red-800 dark:text-red-200 flex items-start">
          <AlertTriangle className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {readOnly && finalization && (
        <div className="rounded-lg border border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20 p-3">
          <div className="flex items-center text-sm font-semibold text-green-800 dark:text-green-200">
            <CheckCircle className="w-4 h-4 mr-2" />
            Feature selection confirmed
          </div>
          <div className="text-xs text-green-900/80 dark:text-green-200/80 mt-1">
            {finalization.features.length} variables selected. Monotone constraints persisted for Step 5.
            {onEditOverrides && (
              <>
                {' '}
                <button className="underline font-medium" onClick={onEditOverrides}>
                  Edit overrides
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Footer - different per phase */}
      {phase === 'select' ? (
        <div className="flex items-center justify-between">
        <div className={`text-xs ${theme.textStrong}`}>
          Final selection = {totalSelected} variables (including{' '}
            {Array.from(included).filter((v) => result.rows.find((r) => r.variable === v)?.locked).length} locked).
          </div>
          <div className="space-x-2">
            {onBack && !readOnly && (
              <button
                onClick={onBack}
              className={`text-xs px-3 py-1.5 rounded border ${theme.panelBorder} ${
                theme.isDarkMode ? 'text-gray-200 bg-slate-900' : 'text-gray-700 bg-white hover:bg-gray-50'
              }`}
              >
                Back to RFE
              </button>
            )}
            <button
              onClick={() => setPhase('monotone')}
              disabled={totalSelected === 0}
              className="text-xs px-3 py-1.5 rounded text-white font-semibold inline-flex items-center disabled:opacity-50"
              style={{ backgroundColor: theme.accent }}
            >
              Confirm &amp; continue
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPhase('select')}
            className={`text-xs px-3 py-1.5 rounded border ${theme.panelBorder} ${
              theme.isDarkMode ? 'text-gray-200 bg-slate-900' : 'text-gray-700 bg-white'
            } inline-flex items-center`}
          >
            <ArrowLeft className="w-3 h-3 mr-1" />
            Back to selection
          </button>
          <div className="space-x-2 flex items-center">
            <button
              onClick={handleExport}
              className={`text-xs px-3 py-1.5 rounded border ${theme.panelBorder} ${
                theme.isDarkMode ? 'text-gray-200 bg-slate-900' : 'text-gray-700 bg-white hover:bg-gray-50'
              } inline-flex items-center`}
            >
              <Download className="w-3 h-3 mr-1" />
              Export RFE log
            </button>
            {readOnly ? (
              <span className="text-xs inline-flex items-center px-2 py-1 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-200">
                <CheckCircle className="w-3 h-3 mr-1" />
                Confirmed
              </span>
            ) : (
              <button
                onClick={handleConfirm}
                disabled={submitting || totalSelected === 0}
                className="text-xs px-3 py-1.5 rounded text-white font-semibold inline-flex items-center disabled:opacity-50"
                style={{ backgroundColor: theme.accent }}
              >
                {submitting ? <Loader className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle className="w-3 h-3 mr-1" />}
                {submitting ? 'Finalizing...' : `Confirm ${totalSelected} variables & continue`}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------- Subcomponents ----------------------

interface TileProps {
  theme: ReturnType<typeof getRfeTheme>;
  label: string;
  value: string;
  accent?: boolean;
}

const Tile: React.FC<TileProps> = ({ theme, label, value, accent }) => (
  <div
    className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} p-3`}
    style={accent ? { boxShadow: `inset 0 0 0 1px ${theme.accent}` } : undefined}
  >
    <div className={`text-[11px] uppercase tracking-wider ${theme.textMuted}`}>{label}</div>
    <div className={`mt-1 text-base font-semibold ${theme.textStrong}`}>{value}</div>
  </div>
);

// ---------- Phase 1: Selection table ----------

interface SelectionPaneProps {
  theme: ReturnType<typeof getRfeTheme>;
  tab: 'retained' | 'dropped' | 'all';
  setTab: (t: 'retained' | 'dropped' | 'all') => void;
  search: string;
  setSearch: (s: string) => void;
  visibleRows: RfeVariableRow[];
  retainedRankMap: Map<string, number>;
  retainedCount: number;
  droppedCount: number;
  totalRows: number;
  nVarHeader: string;
  included: Set<string>;
  toggleVariable: (row: RfeVariableRow) => void;
  readOnly: boolean;
}

const SelectionPane: React.FC<SelectionPaneProps> = ({
  theme,
  tab,
  setTab,
  search,
  setSearch,
  visibleRows,
  retainedRankMap,
  retainedCount,
  droppedCount,
  totalRows,
  nVarHeader,
  included,
  toggleVariable,
  readOnly,
}) => {
  const showLockCol = tab !== 'dropped';
  const showNVarVif = tab !== 'dropped';
  const colCount = tab === 'dropped' ? 7 : 9;
  const theadCell = 'px-3 py-2 font-semibold uppercase tracking-wider text-white/95';

  return (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        {(['retained', 'dropped', 'all'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-xs px-3 py-1.5 rounded border ${theme.panelBorder} ${
              tab === t ? 'text-white' : theme.isDarkMode ? 'text-gray-200 bg-slate-900' : 'text-gray-700 bg-white'
            }`}
            style={tab === t ? { backgroundColor: theme.accent } : {}}
          >
            {t[0].toUpperCase() + t.slice(1)} (
            {t === 'retained' ? retainedCount : t === 'dropped' ? droppedCount : totalRows})
          </button>
        ))}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search variable..."
          className={`ml-auto text-xs px-2 py-1.5 border ${theme.panelBorder} rounded ${
            theme.isDarkMode ? 'bg-slate-900 text-white' : 'bg-white text-gray-800'
          }`}
        />
      </div>

      <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} overflow-hidden`}>
        <div className="max-h-[28rem] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className={`${MTA_THEAD} sticky top-0 z-10`}>
              <tr>
                <th className={`${theadCell} text-left`}>Selection</th>
                <th className={`${theadCell} text-left`}>Variable</th>
                {showLockCol && <th className={`${theadCell} text-left`}>Lock</th>}
                <th className={`${theadCell} text-right`}>IV</th>
                <th className={`${theadCell} text-right`}>|Corr|</th>
                <th className={`${theadCell} text-right`}>Original VIF</th>
                {showNVarVif && <th className={`${theadCell} text-right`}>{nVarHeader}</th>}
                <th className={`${theadCell} text-right`}>SHAP</th>
                <th className={`${theadCell} text-left`}>Rank Trajectory</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.length === 0 && (
                <tr>
                  <td colSpan={colCount} className={`px-3 py-6 text-center ${theme.textMuted}`}>
                    No variables match.
                  </td>
                </tr>
              )}
              {visibleRows.map((row, idx) => {
                const isIncluded = included.has(row.variable);
                const rowBg = idx % 2 === 0 ? theme.tableRow : theme.tableZebra;
                const isRetained = row.status === 'retained';
                const rankK = retainedRankMap.get(row.variable);
                return (
                  <tr key={row.variable} className={rowBg}>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={isIncluded}
                        onChange={() => toggleVariable(row)}
                        disabled={readOnly}
                      />
                    </td>
                    <td className={`px-3 py-2 font-medium ${theme.textStrong}`}>{row.variable}</td>
                    {showLockCol && (
                      <td className="px-3 py-2">
                        {row.locked ? (
                          <span
                            title="Locked - originally marked must-keep"
                            className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-200"
                          >
                            <Lock className="w-3 h-3 mr-1" />
                            locked
                          </span>
                        ) : (
                          <span className={theme.textMuted}>—</span>
                        )}
                      </td>
                    )}
                    <td className={`px-3 py-2 text-right ${theme.textMuted}`}>{fmt(row.iv)}</td>
                    <td className={`px-3 py-2 text-right ${theme.textMuted}`}>{fmt(row.abs_corr_target)}</td>
                    <td className={`px-3 py-2 text-right ${theme.textMuted}`}>{fmt(row.orig_vif, 2)}</td>
                    {showNVarVif && (
                      <td className={`px-3 py-2 text-right ${theme.textStrong}`}>{fmt(row.nvar_vif, 2)}</td>
                    )}
                    <td className={`px-3 py-2 text-right ${theme.textMuted}`}>
                      {fmt(row.shap_importance_best, 4)}
                    </td>
                    <td className="px-3 py-2">
                      <RankSparkline
                        trajectory={row.rank_trajectory}
                        isDarkMode={theme.isDarkMode}
                        variant={isRetained ? 'retained' : 'dropped'}
                        label={isRetained ? (rankK !== undefined ? `#${rankK}` : '—') : 'drop'}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
};

// ---------- Phase 2: Monotone Constraint Configuration ----------

interface MonotoneConfigPaneProps {
  theme: ReturnType<typeof getRfeTheme>;
  rows: RfeVariableRow[];
  included: Set<string>;
  setIncluded: React.Dispatch<React.SetStateAction<Set<string>>>;
  monotone: Record<string, MonotoneDir>;
  setMono: (variable: string, dir: MonotoneDir) => void;
  readOnly: boolean;
}

const MonotoneConfigPane: React.FC<MonotoneConfigPaneProps> = ({
  theme,
  rows,
  included,
  setIncluded,
  monotone,
  setMono,
  readOnly,
}) => {
  const includedRows = useMemo(
    () => rows.filter((r) => included.has(r.variable)),
    [rows, included]
  );
  const theadCell = 'px-3 py-2 font-semibold uppercase tracking-wider text-white/95';

  const toggleIncluded = (variable: string) => {
    if (readOnly) return;
    setIncluded((prev) => {
      const next = new Set(prev);
      if (next.has(variable)) next.delete(variable);
      else next.add(variable);
      return next;
    });
  };

  return (
    <div className="space-y-3">
      <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} p-3`}>
        <div className={`text-sm font-semibold ${theme.textStrong}`}>Monotone constraint configuration</div>
        <div className={`text-[11px] ${theme.textMuted} mt-1 leading-relaxed`}>
          Set expected directionality for each variable. For numeric features the suggestion is
          pre-filled from the bivariate correlation sign. For categorical-origin features
          (WoE-encoded or one-hot) the default is <strong>0</strong> (unconstrained).
          Override per variable: <strong>+1</strong> (higher value increases prediction),{' '}
          <strong>-1</strong> (higher value decreases prediction), <strong>0</strong> (unconstrained).
          Applied to XGBoost, LightGBM and CatBoost only.
        </div>
      </div>

      <div className={`rounded-lg border ${theme.panelBorder} ${theme.panelBg} overflow-hidden`}>
        <div className="max-h-[28rem] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className={`${MTA_THEAD} sticky top-0 z-10`}>
              <tr>
                <th className={`${theadCell} text-left`}>Selection</th>
                <th className={`${theadCell} text-left`}>Variable</th>
                <th className={`${theadCell} text-right`}>Bivariate Correlation</th>
                <th className={`${theadCell} text-center`}>Suggested Direction</th>
                <th className={`${theadCell} text-left`}>Monotone Constraint</th>
              </tr>
            </thead>
            <tbody>
              {includedRows.length === 0 && (
                <tr>
                  <td colSpan={5} className={`px-3 py-6 text-center ${theme.textMuted}`}>
                    No variables selected.
                  </td>
                </tr>
              )}
              {includedRows.map((row, idx) => {
                const rowBg = idx % 2 === 0 ? theme.tableRow : theme.tableZebra;
                const bc = row.bivariate_corr;
                const bcColor =
                  bc === null || bc === undefined || Number.isNaN(bc)
                    ? theme.textMuted
                    : bc > 0
                    ? 'text-emerald-600 dark:text-emerald-300'
                    : bc < 0
                    ? 'text-red-600 dark:text-red-300'
                    : theme.textMuted;
                const bcLabel =
                  bc === null || bc === undefined || Number.isNaN(bc)
                    ? '—'
                    : `${bc >= 0 ? '+' : ''}${bc.toFixed(4)}`;
                const suggested = (row.suggested_monotone ?? 0) as MonotoneDir;
                const suggestedLabel = suggested === 1 ? '+1' : suggested === -1 ? '-1' : '0';
                const suggestedColor =
                  suggested === 1
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'
                    : suggested === -1
                    ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-200'
                    : 'bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-gray-300';
                return (
                  <tr key={row.variable} className={rowBg}>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked
                        onChange={() => toggleIncluded(row.variable)}
                        disabled={readOnly}
                      />
                    </td>
                    <td className={`px-3 py-2 font-medium ${theme.textStrong}`}>{row.variable}</td>
                    <td className={`px-3 py-2 text-right font-mono ${bcColor}`}>{bcLabel}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded ${suggestedColor}`}>
                        {suggestedLabel}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <MonotonePicker
                        value={(monotone[row.variable] ?? 0) as MonotoneDir}
                        onChange={(d) => setMono(row.variable, d)}
                        theme={theme}
                        disabled={readOnly}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ---------- Reusable controls ----------

interface MonotonePickerProps {
  value: MonotoneDir;
  onChange: (dir: MonotoneDir) => void;
  theme: ReturnType<typeof getRfeTheme>;
  disabled?: boolean;
}

const MonotonePicker: React.FC<MonotonePickerProps> = ({ value, onChange, theme, disabled }) => {
  const opts: { v: MonotoneDir; label: string }[] = [
    { v: -1, label: '−1' },
    { v: 0, label: '0' },
    { v: 1, label: '+1' },
  ];
  return (
    <div
      className="inline-flex rounded border overflow-hidden"
      style={{ borderColor: theme.isDarkMode ? '#334155' : '#e5e7eb' }}
    >
      {opts.map((opt) => {
        const selected = value === opt.v;
        return (
          <button
            key={opt.v}
            onClick={() => onChange(opt.v)}
            disabled={disabled}
            className={`px-2 py-1 text-[11px] ${disabled ? 'opacity-40' : ''} ${
              selected
                ? 'text-white'
                : theme.isDarkMode
                ? 'text-gray-200 bg-slate-900'
                : 'text-gray-700 bg-white'
            }`}
            style={selected ? { backgroundColor: theme.accent } : {}}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
};

interface RankSparklineProps {
  trajectory: Array<number | null>;
  isDarkMode: boolean;
  variant: 'retained' | 'dropped';
  label: string;
}

const RankSparkline: React.FC<RankSparklineProps> = ({ trajectory, isDarkMode, variant, label }) => {
  const W = 90;
  const H = 24;
  const stroke = variant === 'retained' ? '#16A34A' : '#DC2626';
  const badgeText =
    variant === 'retained'
      ? 'text-emerald-600 dark:text-emerald-300'
      : 'text-red-600 dark:text-red-300';
  const cleaned = trajectory.filter((v) => v !== null && v !== undefined) as number[];
  if (cleaned.length === 0) {
    return (
      <div className="inline-flex items-center gap-1">
        <span className={`text-[11px] ${isDarkMode ? 'text-gray-400' : 'text-gray-400'}`}>—</span>
        <span className={`text-[10px] font-semibold ${badgeText}`}>{label}</span>
      </div>
    );
  }
  const maxRank = Math.max(...cleaned, 1);
  const minRank = Math.min(...cleaned, 1);
  const range = Math.max(1, maxRank - minRank);
  const stepX = trajectory.length > 1 ? W / (trajectory.length - 1) : W;
  const points: string[] = [];
  trajectory.forEach((v, i) => {
    if (v === null || v === undefined) return;
    const x = i * stepX;
    const y = ((v - minRank) / range) * (H - 4) + 2;
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  });
  return (
    <div className="inline-flex items-center gap-2">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block">
        <rect width={W} height={H} fill="transparent" />
        {points.length > 1 && (
          <polyline points={points.join(' ')} fill="none" stroke={stroke} strokeWidth={1.5} />
        )}
        {points.map((p, i) => {
          const [x, y] = p.split(',').map(Number);
          return <circle key={i} cx={x} cy={y} r={1.4} fill={stroke} />;
        })}
      </svg>
      <span className={`text-[10px] font-semibold ${badgeText}`}>{label}</span>
    </div>
  );
};

export default FeatureReviewStep;
