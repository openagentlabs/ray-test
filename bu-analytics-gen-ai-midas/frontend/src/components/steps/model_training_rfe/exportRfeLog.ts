/**
 * Utility to build and download the RFE log CSV from a finalized result plus
 * the current Step 4 selection / monotone state.
 *
 * Output format: a single CSV with two labelled sections separated by a blank
 * line. Section A = iteration log (Step 3), Section B = variable rows (Step 4).
 */

import type { RfeResultResponse, RfeVariableRow } from '../../../services/rfeService';

type MonotoneDir = -1 | 0 | 1;

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = String(value);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function fmtNum(value: number | null | undefined, digits = 6): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '';
  return value.toFixed(digits);
}

function iterStatusLabel(
  iter: RfeResultResponse['iterations'][number],
  prev: RfeResultResponse['iterations'][number] | null,
): string {
  if (iter.iteration === 0) return 'Baseline';
  if (iter.is_best) return 'Best';
  if (iter.stop_reason) return 'Stop';
  const delta = iter.relative_delta_from_prev;
  if (delta !== null && delta !== undefined && delta < 0) return 'Degraded';
  void prev;
  return '';
}

function buildFinalRankMap(rows: RfeVariableRow[]): Map<string, number> {
  const retained = rows.filter((r) => r.status === 'retained');
  const withRank = retained.map((r) => {
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
  withRank.sort((a, b) => (a.rank - b.rank) || a.variable.localeCompare(b.variable));
  const map = new Map<string, number>();
  withRank.forEach((r, idx) => map.set(r.variable, idx + 1));
  return map;
}

export function buildRfeLogCsv(
  result: RfeResultResponse,
  included: Set<string>,
  monotone: Record<string, MonotoneDir>,
): string {
  const lines: string[] = [];

  lines.push('# Section: Iteration log');
  lines.push(
    [
      'iteration',
      'features_count',
      'dropped_features',
      'elim_rate_pct',
      'cv_auc',
      'test_auc',
      'delta_vs_prev_pct',
      'status',
    ].join(','),
  );
  const iters = result.iterations || [];
  for (let i = 0; i < iters.length; i += 1) {
    const it = iters[i];
    const prev = i > 0 ? iters[i - 1] : null;
    const elimRate = prev && prev.feature_count > 0
      ? ((prev.feature_count - it.feature_count) / prev.feature_count) * 100
      : null;
    const deltaPct = it.relative_delta_from_prev !== null && it.relative_delta_from_prev !== undefined
      ? it.relative_delta_from_prev * 100
      : null;
    const status = iterStatusLabel(it, prev);
    lines.push(
      [
        csvEscape(it.iteration),
        csvEscape(it.feature_count),
        csvEscape((it.features_dropped || []).join('; ')),
        csvEscape(elimRate === null ? '' : fmtNum(elimRate, 2)),
        csvEscape(fmtNum(it.cv_auc, 6)),
        csvEscape(fmtNum(it.test_auc, 6)),
        csvEscape(deltaPct === null ? '' : fmtNum(deltaPct, 4)),
        csvEscape(status),
      ].join(','),
    );
  }

  lines.push('');
  lines.push('# Section: Variable rows');
  lines.push(
    [
      'variable',
      'status',
      'locked',
      'included',
      'drop_iteration',
      'iv',
      'abs_corr',
      'orig_vif',
      'nvar_vif',
      'shap_best',
      'final_rank',
      'bivariate_corr',
      'suggested_monotone',
      'user_monotone',
    ].join(','),
  );

  const rankMap = buildFinalRankMap(result.rows || []);
  for (const row of result.rows || []) {
    const isIncluded = included.has(row.variable);
    const userMono = monotone[row.variable] ?? 0;
    const finalRank = row.status === 'retained' ? rankMap.get(row.variable) : null;
    lines.push(
      [
        csvEscape(row.variable),
        csvEscape(row.status),
        csvEscape(row.locked ? 'true' : 'false'),
        csvEscape(isIncluded ? 'true' : 'false'),
        csvEscape(row.drop_iteration === null || row.drop_iteration === undefined ? '' : row.drop_iteration),
        csvEscape(fmtNum(row.iv, 6)),
        csvEscape(fmtNum(row.abs_corr_target, 6)),
        csvEscape(fmtNum(row.orig_vif, 4)),
        csvEscape(fmtNum(row.nvar_vif, 4)),
        csvEscape(fmtNum(row.shap_importance_best, 6)),
        csvEscape(finalRank === null || finalRank === undefined ? '' : finalRank),
        csvEscape(fmtNum(row.bivariate_corr, 6)),
        csvEscape(row.suggested_monotone ?? 0),
        csvEscape(userMono),
      ].join(','),
    );
  }

  return lines.join('\n');
}

export function downloadRfeLogCsv(
  result: RfeResultResponse,
  included: Set<string>,
  monotone: Record<string, MonotoneDir>,
): void {
  const csv = buildRfeLogCsv(result, included, monotone);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `rfe_log_${result.job_id || 'export'}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
