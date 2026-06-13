/**
 * Build the JSON payload for the cross-algorithm LLM recommendation endpoint
 * (same candidate selection as "Model recommendations (max 2 per algorithm)").
 */

import { resolveNonzeroFeatureCount, resolveTrainingBundleUsedFeatures } from './modelScreenerUtils';

export type CrossAlgorithmCandidatePayload = {
  algorithm: string;
  guideline: string;
  segment_id: string | null;
  model_id: string;
  best_iteration: number | string | null;
  train_primary: number | null;
  test_primary: number | null;
  ks_train: number | null;
  ks_test: number | null;
  overfit_pct: number | null;
  feature_display: string;
  flags: string;
};

export type CrossAlgorithmLrDigest = {
  algorithm: string;
  segment_id: string | null;
  status: string | null;
  matched_count: number | null;
  mismatched_count: number | null;
  sample_mismatch_features: string[];
};

function getFirstFinite(metricObj: any, keys: string[]): number | null {
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

function formatNonZeroRatio(nz: number | null, total: number | null): string {
  if (nz !== null && total !== null && total > 0) return `${Math.round(nz)}/${Math.round(total)}`;
  if (nz !== null) return `${Math.round(nz)}`;
  return 'N/A';
}

/** Returns null if there are no recommendation rows to summarize. */
export function buildStep6CrossAlgorithmPayload(
  results: any,
  g1Rows: any[],
  g2Rows: any[],
  lrRows: any[],
  problemType: string,
): { candidates: CrossAlgorithmCandidatePayload[]; lr_digest: CrossAlgorithmLrDigest[] } | null {
  const modelLookup = new Map<string, any>();
  const sourceRows: any[] = [];
  if (Array.isArray(results?.results)) {
    sourceRows.push(...results.results);
  }
  if (results?.segment_results && typeof results.segment_results === 'object') {
    Object.entries(results.segment_results).forEach(([segmentKey, segPayload]: [string, any]) => {
      const segmentId = String(segmentKey || '').replace('segment_', '');
      (segPayload?.results || []).forEach((r: any) => sourceRows.push({ ...r, segment_id: segmentId }));
    });
  }
  sourceRows.forEach((r: any) => {
    const key = `${String(r?.model_id || '')}__${String(r?.segment_id || '')}`;
    modelLookup.set(key, r);
  });

  const allRows = [
    ...g1Rows.map((r: any) => ({ ...r, guideline: 'G1' })),
    ...g2Rows.map((r: any) => ({ ...r, guideline: 'G2' })),
  ];

  const grouped = new Map<string, any[]>();
  allRows.forEach((row: any) => {
    const key = `${String(row.algorithm || '').toLowerCase()}__${String(row.segment_id || '')}`;
    const arr = grouped.get(key) || [];
    arr.push(row);
    grouped.set(key, arr);
  });

  const recRows: any[] = [];
  grouped.forEach((rows) => {
    const sorted = [...rows].sort((a, b) => {
      const g = String(a.guideline).localeCompare(String(b.guideline));
      if (g !== 0) return g;
      return (Number(b.score) || -Infinity) - (Number(a.score) || -Infinity);
    });
    recRows.push(...sorted.slice(0, 2));
  });

  if (recRows.length === 0) return null;

  const isCls = problemType === 'classification';
  const candidates: CrossAlgorithmCandidatePayload[] = recRows.map((row: any) => {
    const model = modelLookup.get(`${String(row?.model_id || '')}__${String(row?.segment_id || '')}`) || {};
    const metrics = model?.metrics || {};
    const trainPrimary = isCls
      ? getFirstFinite(metrics, ['train_auc']) ?? getFirstFinite(row, ['train_score'])
      : getFirstFinite(metrics, ['train_r2']) ?? getFirstFinite(row, ['train_score']);
    const testPrimary = isCls
      ? getFirstFinite(metrics, ['test_auc', 'auc']) ?? getFirstFinite(row, ['score'])
      : getFirstFinite(metrics, ['test_r2', 'r2']) ?? getFirstFinite(row, ['score']);
    const ksTr = getFirstFinite(metrics, ['train_ks_statistic', 'ks_statistic']);
    const ksTe = getFirstFinite(metrics, ['test_ks_statistic', 'ks_statistic']);
    const overfitPct =
      getFirstFinite(row, ['overfit_pct']) ?? getFirstFinite(metrics, ['overfit_pct']) ?? calcOverfitPct(trainPrimary, testPrimary);
    const bundleUF = resolveTrainingBundleUsedFeatures(results, row?.segment_id ?? model?.segment_id);
    const totalFeat =
      getFirstFinite(metrics, ['feature_count']) ??
      getFirstFinite(row, ['feature_count']) ??
      (Array.isArray(model?.used_features) ? model.used_features.length : null) ??
      (Array.isArray(bundleUF) ? bundleUF.length : null);
    const nzFeat =
      resolveNonzeroFeatureCount(model, { ...metrics, ...row }, bundleUF) ??
      getFirstFinite(metrics, ['feature_importance_count']) ??
      getFirstFinite(row, ['feature_importance_count']);
    const featDisplay = formatNonZeroRatio(nzFeat, totalFeat);
    const flags = row?.is_recommended
      ? 'Best overall'
      : overfitPct !== null && overfitPct > 10
        ? 'Overfit >10%'
        : String(row.algorithm || '').toLowerCase().includes('logistic')
          ? 'Post-elim'
          : '-';

    return {
      algorithm: String(row.algorithm || ''),
      guideline: String(row.guideline || ''),
      segment_id: row.segment_id != null && row.segment_id !== '' ? String(row.segment_id) : null,
      model_id: String(row.model_id || ''),
      best_iteration: row.best_iteration ?? row.iteration ?? null,
      train_primary: trainPrimary,
      test_primary: testPrimary,
      ks_train: ksTr,
      ks_test: ksTe,
      overfit_pct: overfitPct,
      feature_display: featDisplay,
      flags,
    };
  });

  const lr_digest: CrossAlgorithmLrDigest[] = (Array.isArray(lrRows) ? lrRows : []).slice(0, 12).map((row: any) => {
    const details = Array.isArray(row.details) ? row.details : [];
    const mismatches = details.filter((d: any) => String(d?.status || '').toLowerCase().includes('mismatch'));
    const sample_mismatch_features = mismatches
      .slice(0, 5)
      .map((d: any) => String(d.feature || d.variable || '').trim())
      .filter(Boolean);
    return {
      algorithm: String(row.algorithm || ''),
      segment_id: row.segment_id != null && row.segment_id !== '' ? String(row.segment_id) : null,
      status: row.status != null ? String(row.status) : null,
      matched_count: typeof row.matched_count === 'number' ? row.matched_count : null,
      mismatched_count: typeof row.mismatched_count === 'number' ? row.mismatched_count : null,
      sample_mismatch_features,
    };
  });

  return { candidates, lr_digest };
}
