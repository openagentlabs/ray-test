import React from 'react';
import { GitBranch, TreePine, Sigma, Loader2 } from 'lucide-react';
import { MTA_SECTION, MTA_TITLE_SECTION } from './modelTrainingMtaUi';

export type Step6PipelinePath = 'tree' | 'lr';

export type LrBackwardEliminationRow = {
  iteration: number;
  phase: string;
  variable_removed?: string | null;
  reason?: string | null;
  offending_value?: number | null;
  threshold?: string | null;
  remaining_features?: number | null;
  test_auc?: number | null;
  /** In-sample train AUC when test holdout is unavailable or alongside test. */
  train_auc?: number | null;
  locked_flags?: string | null;
};

export type LrBackwardReport = {
  algorithm?: string;
  model_id?: string;
  iterations?: LrBackwardEliminationRow[];
  summary?: Record<string, unknown>;
  config?: { vif_threshold?: number; p_value_threshold?: number };
};

type Props = {
  pipelinePath: Step6PipelinePath;
  onPipelinePathChange: (p: Step6PipelinePath) => void;
  /** When user selects LR, parent runs on-demand elimination (optional). */
  onRunLrElimination?: () => void | Promise<void>;
  lrReport: LrBackwardReport | null | undefined;
  trainingLrConfig?: { vif_threshold?: number; p_value_threshold?: number } | null;
  startingFeatureCount?: number | null;
  liveLoading?: boolean;
  liveError?: string | null;
};

const phaseBadge = (phase: string) => {
  const p = String(phase || '').toLowerCase();
  if (p === 'baseline') return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200';
  if (p.includes('vif')) return 'bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-200';
  if (p.includes('p_value') || p.includes('p-val')) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-100';
  return 'bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-gray-200';
};

const fmt = (v: unknown, digits = 4): string => {
  if (typeof v === 'number' && Number.isFinite(v)) return v.toFixed(digits);
  if (v === null || v === undefined) return '—';
  return String(v);
};

function pickNum(row: LrBackwardEliminationRow, ...keys: string[]): number | null {
  const anyRow = row as Record<string, unknown>;
  for (const k of keys) {
    const v = anyRow[k];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
    if (typeof v === 'string' && v.trim() !== '') {
      const n = Number(v);
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}

export const Step6PipelineForkLrSection: React.FC<Props> = ({
  pipelinePath,
  onPipelinePathChange,
  onRunLrElimination,
  lrReport,
  trainingLrConfig,
  startingFeatureCount,
  liveLoading = false,
  liveError = null,
}) => {
  const vifTh = trainingLrConfig?.vif_threshold ?? lrReport?.config?.vif_threshold ?? 5;
  const pTh = trainingLrConfig?.p_value_threshold ?? lrReport?.config?.p_value_threshold ?? 0.05;
  const iterations = Array.isArray(lrReport?.iterations) ? lrReport!.iterations! : [];
  const summary = lrReport?.summary || {};
  const startFeat =
    typeof summary.starting_features === 'number'
      ? summary.starting_features
      : startingFeatureCount ?? (iterations[0]?.remaining_features ?? null);

  return (
    <div className={`mb-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-indigo-50/70 via-white to-white dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md">
          <GitBranch className="h-6 w-6" />
        </div>
        <h4 className={`${MTA_TITLE_SECTION} !text-base md:!text-lg`}>Pipeline Fork: Tree vs. Logistic Regression</h4>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-300 mb-3">
        After Iteration 0, choose how variable sets proceed before Bayesian tuning. Selecting <strong>Logistic Regression</strong> runs §7.2 backward elimination on the server using the same preprocess and train/holdout split as training.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => onPipelinePathChange('tree')}
          className={`text-left rounded-lg border p-3 transition ${
            pipelinePath === 'tree'
              ? 'border-emerald-500 ring-2 ring-emerald-400/40 bg-emerald-50/80 dark:bg-emerald-950/40'
              : 'border-gray-200 dark:border-slate-700 hover:border-emerald-300'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <TreePine className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-semibold text-gray-900 dark:text-white">Tree-based models</span>
            {pipelinePath === 'tree' && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-200 text-emerald-900 dark:bg-emerald-800 dark:text-emerald-100">Selected</span>
            )}
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-300">
            Proceed directly to Bayesian hyperparameter tuning with the full retained feature set (e.g. XGBoost, LightGBM, CatBoost). Tree models tolerate multicollinearity; no LR-style elimination pass.
          </p>
        </button>

        <button
          type="button"
          onClick={() => {
            onPipelinePathChange('lr');
            void Promise.resolve(onRunLrElimination?.());
          }}
          className={`text-left rounded-lg border p-3 transition ${
            pipelinePath === 'lr'
              ? 'border-indigo-500 ring-2 ring-indigo-400/40 bg-indigo-50/80 dark:bg-indigo-950/40'
              : 'border-gray-200 dark:border-slate-700 hover:border-indigo-300'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <Sigma className="h-4 w-4 text-indigo-600" />
            <span className="text-sm font-semibold text-gray-900 dark:text-white">Logistic Regression</span>
            {pipelinePath === 'lr' && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-indigo-200 text-indigo-900 dark:bg-indigo-800 dark:text-indigo-100">Selected</span>
            )}
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-300">
            Backward elimination first (VIF &gt; {vifTh}, then p-value &gt; {pTh}, one variable at a time). Surviving features then go to Bayesian tuning (C, penalty, solver). Locked variables are never removed; no minimum feature floor.
          </p>
        </button>
      </div>

      {pipelinePath === 'lr' && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg border border-sky-200 dark:border-sky-900 bg-sky-50/80 dark:bg-sky-950/30 px-3 py-2 text-xs text-sky-900 dark:text-sky-100">
            <div className="font-semibold mb-1">Elimination rules (§7.2)</div>
            <ol className="list-decimal list-inside space-y-1 text-sky-900/90 dark:text-sky-100/90">
              <li>
                <strong>VIF pass:</strong> refit LR; if any VIF &gt; {vifTh}, drop the highest among <em>non-locked</em> variables; repeat until all VIFs ≤ {vifTh}.
              </li>
              <li>
                <strong>p-value pass:</strong> refit LR; if any p-value &gt; {pTh}, drop the highest p among <em>non-locked</em> variables; repeat until all p-values ≤ {pTh}.
              </li>
            </ol>
            <p className="mt-1 text-sky-800 dark:text-sky-200/90">Locked variables are never removed. There is no minimum feature floor.</p>
          </div>

          {liveError && (
            <div className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50/90 dark:bg-red-950/40 px-3 py-2 text-xs text-red-900 dark:text-red-100">
              {liveError}
            </div>
          )}

          {liveLoading && (
            <div className="flex items-center gap-2 text-xs text-indigo-700 dark:text-indigo-300">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <span>Running backward elimination…</span>
            </div>
          )}

          {iterations.length > 0 ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                <div className="rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900/80">
                  <div className="text-[10px] uppercase text-gray-500 dark:text-gray-400">Starting</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">{startFeat ?? '—'}</div>
                  <div className="text-[10px] text-gray-500">From retained set</div>
                </div>
                <div className="rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900/80">
                  <div className="text-[10px] uppercase text-gray-500 dark:text-gray-400">Final</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {typeof summary.final_features === 'number' ? summary.final_features : iterations[iterations.length - 1]?.remaining_features ?? '—'}
                  </div>
                  <div className="text-[10px] text-gray-500">After elimination</div>
                </div>
                <div className="rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900/80">
                  <div className="text-[10px] uppercase text-gray-500 dark:text-gray-400">VIF removals</div>
                  <div className="text-lg font-semibold text-violet-700 dark:text-violet-300">{String(summary.vif_removals ?? '—')}</div>
                </div>
                <div className="rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900/80">
                  <div className="text-[10px] uppercase text-gray-500 dark:text-gray-400">p-value removals</div>
                  <div className="text-lg font-semibold text-amber-700 dark:text-amber-300">{String(summary.p_value_removals ?? '—')}</div>
                </div>
                <div className="rounded border border-gray-200 dark:border-slate-700 p-2 bg-gray-50 dark:bg-slate-900/80">
                  <div className="text-[10px] uppercase text-gray-500 dark:text-gray-400">Iterations</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">{String(summary.elimination_iterations ?? Math.max(0, iterations.length - 1))}</div>
                  <div className="text-[10px] text-gray-500">Including baseline</div>
                </div>
              </div>

              <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
                <table className="w-full min-w-[820px] text-xs">
                  <thead className="bg-gray-50 dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700">
                    <tr>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">PHASE</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">VARIABLE REMOVED</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">REASON</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">OFFENDING VALUE</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">THRESHOLD</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">REMAINING FEAT.</th>
                      <th className="px-2 py-2 text-left font-semibold text-indigo-700 dark:text-indigo-300">AUC (TEST)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                    {iterations.map((row, idx) => {
                      const off = row.offending_value;
                      const showRed =
                        typeof off === 'number' &&
                        row.phase &&
                        String(row.phase).toLowerCase() !== 'baseline' &&
                        row.variable_removed;
                      const aucTe = pickNum(row, 'test_auc', 'testAuc');
                      const aucTr = pickNum(row, 'train_auc', 'trainAuc');
                      const aucDisplay = aucTe != null ? aucTe : aucTr;
                      return (
                        <React.Fragment key={`lr_elim_${row.iteration}_${idx}`}>
                          <tr className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                            <td className="px-2 py-2 whitespace-nowrap">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${phaseBadge(row.phase)}`}>
                                {String(row.phase || '').replace(/_/g, ' ')}
                              </span>
                            </td>
                            <td className="px-2 py-2 whitespace-nowrap text-gray-800 dark:text-gray-100">{row.variable_removed ?? '—'}</td>
                            <td className="px-2 py-2 text-gray-700 dark:text-gray-200">{row.reason ?? '—'}</td>
                            <td className={`px-2 py-2 whitespace-nowrap ${showRed ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-800 dark:text-gray-100'}`}>
                              {typeof off === 'number' ? (row.phase?.toLowerCase().includes('p_value') ? off.toFixed(4) : off.toFixed(2)) : '—'}
                            </td>
                            <td className="px-2 py-2 whitespace-nowrap text-gray-700 dark:text-gray-200">{row.threshold ?? '—'}</td>
                            <td className="px-2 py-2 whitespace-nowrap text-gray-800 dark:text-gray-100">{row.remaining_features ?? '—'}</td>
                            <td className="px-2 py-2 whitespace-nowrap text-gray-800 dark:text-gray-100">
                              {aucDisplay != null ? fmt(aucDisplay, 4) : '—'}
                            </td>
                          </tr>
                          {String(row.phase).toLowerCase().includes('vif') &&
                            idx < iterations.length - 1 &&
                            String(iterations[idx + 1]?.phase || '')
                              .toLowerCase()
                              .includes('p_value') && (
                              <tr>
                                <td colSpan={7} className="px-2 py-1.5 text-[11px] bg-violet-50/80 dark:bg-violet-950/30 text-violet-900 dark:text-violet-200 border-t border-violet-100 dark:border-violet-900">
                                  ✓ VIF pass complete. Proceeding to p-value pass.
                                </td>
                              </tr>
                            )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {typeof summary.narrative === 'string' && summary.narrative && (
                <div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50/90 dark:bg-emerald-950/40 px-3 py-2 text-xs text-emerald-900 dark:text-emerald-100">
                  ✓ {summary.narrative}
                </div>
              )}
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-gray-300 dark:border-slate-600 p-4 text-center text-xs text-gray-600 dark:text-gray-400">
              {liveLoading
                ? 'Computing audit rows…'
                : 'Select Logistic Regression above to run backward elimination on the current feature set, or complete a training run that includes LR to merge server-side audit data.'}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Step6PipelineForkLrSection;
