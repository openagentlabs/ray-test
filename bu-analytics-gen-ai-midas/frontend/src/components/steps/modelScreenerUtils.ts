/**
 * Shared helpers for Model Evaluation screener (Step 5) — mirrors MTA manual screener logic.
 */

export type ModelFilterRow = {
  metric: string;
  operator: '>=' | '<=' | '>' | '<' | '==';
  value: string;
};

/** First finite numeric among keys (matches screener / pruning table fallbacks). */
export function getFirstFiniteFromMetrics(metricObj: any, keys: string[]): number | undefined {
  if (!metricObj || typeof metricObj !== 'object') return undefined;
  for (const key of keys) {
    const raw = (metricObj as Record<string, unknown>)[key];
    if (raw === null || raw === undefined) continue;
    if (typeof raw === 'string' && raw.trim() === '') continue;
    const val = typeof raw === 'number' ? raw : Number(raw);
    if (Number.isFinite(val)) return val;
  }
  return undefined;
}

const TEST_AUC_KEYS = ['test_auc', 'auc_test', 'auc'] as const;
/** Train-only names; omit bare `auc` so it is not reused as train when it represents test/holdout. */
const TRAIN_AUC_KEYS = ['train_auc', 'auc_train'] as const;
const TEST_KS_KEYS = ['test_ks_statistic', 'ks_test', 'ks_statistic'] as const;
const TRAIN_KS_KEYS = ['train_ks_statistic', 'ks_train'] as const;
const TEST_ACC_KEYS = ['test_accuracy', 'accuracy_test', 'accuracy'] as const;
const TRAIN_ACC_KEYS = ['train_accuracy', 'accuracy_train', 'accuracy'] as const;
const TEST_R2_KEYS = ['test_r2', 'r2_test', 'r2'] as const;
const TRAIN_R2_KEYS = ['train_r2', 'r2_train', 'r2'] as const;
const TEST_MAE_KEYS = ['test_mae', 'mae_test', 'mae'] as const;
const TRAIN_MAE_KEYS = ['train_mae', 'mae_train', 'mae'] as const;
const TEST_MSE_KEYS = ['test_mse', 'mse_test', 'mse'] as const;
const TRAIN_MSE_KEYS = ['train_mse', 'mse_train', 'mse'] as const;
const TEST_RMSE_KEYS = ['test_rmse', 'rmse_test', 'rmse'] as const;
const TRAIN_RMSE_KEYS = ['train_rmse', 'rmse_train', 'rmse'] as const;

function approxEqual(a: number, b: number): boolean {
  const scale = Math.max(1, Math.abs(a), Math.abs(b));
  return Math.abs(a - b) <= 1e-5 * scale;
}

function resolveScalarForScreenerFilter(metrics: Record<string, any>, filterMetric: string): number | undefined {
  const chainMap: Record<string, readonly string[]> = {
    test_auc: TEST_AUC_KEYS,
    train_auc: [...TRAIN_AUC_KEYS, 'auc'],
    test_ks_statistic: TEST_KS_KEYS,
    train_ks_statistic: TRAIN_KS_KEYS,
    test_accuracy: TEST_ACC_KEYS,
    train_accuracy: TRAIN_ACC_KEYS,
    test_r2: TEST_R2_KEYS,
    train_r2: TRAIN_R2_KEYS,
    test_mae: TEST_MAE_KEYS,
    train_mae: TRAIN_MAE_KEYS,
    test_mse: TEST_MSE_KEYS,
    train_mse: TRAIN_MSE_KEYS,
    test_rmse: TEST_RMSE_KEYS,
    train_rmse: TRAIN_RMSE_KEYS,
    ks_statistic: TEST_KS_KEYS,
    auc: TEST_AUC_KEYS,
    accuracy: TEST_ACC_KEYS,
    r2: TEST_R2_KEYS,
    mae: TEST_MAE_KEYS,
    mse: TEST_MSE_KEYS,
    rmse: TEST_RMSE_KEYS,
  };
  const chain = chainMap[filterMetric];
  if (chain) return getFirstFiniteFromMetrics(metrics, [...chain]);
  const direct = metrics[filterMetric];
  if (direct === null || direct === undefined) return undefined;
  if (typeof direct === 'string' && direct.trim() === '') return undefined;
  const n = typeof direct === 'number' ? direct : Number(direct);
  return Number.isFinite(n) ? n : undefined;
}

export function getPrimaryMetricKey(problemType: string, targetMetric: string = ''): string {
  if (!targetMetric) {
    return problemType === 'classification' ? 'auc' : 'r2';
  }
  const metricMapping: Record<string, string> = {
    auc: 'auc',
    f1: 'f1',
    precision: 'precision',
    recall: 'recall',
    accuracy: 'accuracy',
    log_loss: 'log_loss',
    r2: 'r2',
    mae: 'mae',
    mse: 'mse',
    rmse: 'rmse',
  };
  return metricMapping[targetMetric] || (problemType === 'classification' ? 'auc' : 'r2');
}

export function getBestMetricsFromHistory(result: any, problemType: string, targetMetric: string = ''): any {
  if (!result.iteration_history || !Array.isArray(result.iteration_history) || result.iteration_history.length === 0) {
    return result.metrics || {};
  }
  const scoreKey = getPrimaryMetricKey(problemType, targetMetric);
  const bestIteration = result.iteration_history.reduce((best: any, current: any) => {
    const currentScore =
      current.metrics?.[scoreKey] !== undefined
        ? current.metrics[scoreKey]
        : typeof current.score === 'number'
          ? current.score
          : 0;
    const bestScore =
      best.metrics?.[scoreKey] !== undefined
        ? best.metrics[scoreKey]
        : typeof best.score === 'number'
          ? best.score
          : 0;
    return currentScore > bestScore ? current : best;
  }, {});

  return {
    ...result.metrics,
    ...(bestIteration.metrics || {}),
    feature_importance_count: bestIteration.feature_importance_count || result.metrics?.feature_importance_count,
  };
}

export function collectResultsToProcess(trainingResults: any, segmentFilter: string): any[] {
  if (!trainingResults) return [];
  if (trainingResults.segment_results) {
    const segmentsToProcess =
      segmentFilter === 'all' ? trainingResults.segments || [] : [segmentFilter];
    const out: any[] = [];
    for (const segmentId of segmentsToProcess) {
      const segmentKey = `segment_${segmentId}`;
      const segmentResult = trainingResults.segment_results[segmentKey];
      if (segmentResult?.results) {
        segmentResult.results.forEach((result: any) => {
          out.push({ ...result, segment_id: segmentId });
        });
      }
    }
    return out;
  }
  return Array.isArray(trainingResults.results) ? trainingResults.results : [];
}

function metricPasses(
  metrics: Record<string, any>,
  filter: ModelFilterRow,
): boolean {
  let metricValue: number | undefined;
  if (filter.metric === 'accuracy_diff') {
    const train = getFirstFiniteFromMetrics(metrics, [...TRAIN_ACC_KEYS]);
    const test = getFirstFiniteFromMetrics(metrics, [...TEST_ACC_KEYS]);
    metricValue =
      train !== undefined && test !== undefined && train !== 0
        ? ((train - test) / train) * 100
        : undefined;
  } else if (filter.metric === 'auc_diff') {
    const train = getFirstFiniteFromMetrics(metrics, [...TRAIN_AUC_KEYS]);
    const test = getFirstFiniteFromMetrics(metrics, [...TEST_AUC_KEYS]);
    metricValue =
      train !== undefined && test !== undefined && train !== 0
        ? ((train - test) / train) * 100
        : undefined;
  } else if (filter.metric === 'ks_statistic_diff') {
    const train = getFirstFiniteFromMetrics(metrics, [...TRAIN_KS_KEYS]);
    const test = getFirstFiniteFromMetrics(metrics, [...TEST_KS_KEYS]);
    metricValue =
      train !== undefined && test !== undefined && train !== 0
        ? ((train - test) / train) * 100
        : undefined;
  } else {
    metricValue = resolveScalarForScreenerFilter(metrics, filter.metric);
  }
  const filterValue = parseFloat(filter.value);
  if (metricValue === undefined || metricValue === null || Number.isNaN(metricValue) || Number.isNaN(filterValue)) {
    return false;
  }
  switch (filter.operator) {
    case '>=':
      return metricValue >= filterValue;
    case '<=':
      return metricValue <= filterValue;
    case '>':
      return metricValue > filterValue;
    case '<':
      return metricValue < filterValue;
    case '==':
      return approxEqual(metricValue, filterValue);
    default:
      return true;
  }
}

/**
 * Filter an arbitrary model pool (training rows + pruned queue extras) by algorithm
 * and metric filters. When an algorithm is selected, iteration rows are expanded only
 * if ``iteration_history`` exists; otherwise the best-metrics row is used (pruned /
 * synthetic models).
 */
export function computeFilteredModelsFromPool(
  resultsToProcess: any[],
  problemType: string,
  modelFilters: ModelFilterRow[],
  selectedAlgorithmFilter: string,
): any[] {
  const filtered: any[] = [];

  resultsToProcess.forEach((model: any) => {
    if (selectedAlgorithmFilter && model.algorithm !== selectedAlgorithmFilter) {
      return;
    }
    if (selectedAlgorithmFilter) {
      if (model.iteration_history && Array.isArray(model.iteration_history) && model.iteration_history.length > 0) {
        model.iteration_history.forEach((iteration: any, index: number) => {
          const parentMetrics = model.metrics && typeof model.metrics === 'object' ? model.metrics : {};
          const itMetrics = iteration.metrics && typeof iteration.metrics === 'object' ? iteration.metrics : {};
          const mergedMetrics = { ...parentMetrics, ...itMetrics };
          const iterationModel = {
            ...model,
            iteration_id: index + 1,
            iteration_data: iteration,
            metrics: mergedMetrics,
            hyperparameters: iteration.hyperparameters || {},
            model_id: `${model.model_id}_iteration_${iteration.iteration}`,
            is_iteration: true,
            segment_id: model.segment_id,
          };
          const passesFilters = modelFilters.every((filter) => metricPasses(iterationModel.metrics, filter));
          if (passesFilters) filtered.push(iterationModel);
        });
      } else {
        const bestMetrics = getBestMetricsFromHistory(model, problemType);
        const passesFilters = modelFilters.every((filter) => metricPasses(bestMetrics, filter));
        if (passesFilters) filtered.push(model);
      }
    } else {
      const bestMetrics = getBestMetricsFromHistory(model, problemType);
      const passesFilters = modelFilters.every((filter) => metricPasses(bestMetrics, filter));
      if (passesFilters) filtered.push(model);
    }
  });
  return filtered;
}

export function computeFilteredModels(
  trainingResults: any,
  modelFilters: ModelFilterRow[],
  selectedAlgorithmFilter: string,
  segmentFilter: string,
): any[] {
  if (!trainingResults) return [];
  const problemType = trainingResults.problem_type || 'classification';
  const resultsToProcess = collectResultsToProcess(trainingResults, segmentFilter);
  return computeFilteredModelsFromPool(resultsToProcess, problemType, modelFilters, selectedAlgorithmFilter);
}

function getFirstSampleTrainingModel(trainingResults: any): any | null {
  if (!trainingResults) return null;
  const segs = trainingResults.segment_results;
  if (segs && typeof segs === 'object') {
    const ids: string[] =
      Array.isArray(trainingResults.segments) && trainingResults.segments.length > 0
        ? trainingResults.segments.map((s: any) => String(s))
        : Object.keys(segs).map((k) => String(k).replace(/^segment_/, ''));
    for (const segmentId of ids) {
      const sr = segs[`segment_${segmentId}`];
      const first = sr?.results?.[0];
      if (first) return first;
    }
    const firstKey = Object.keys(segs)[0];
    const first = firstKey && segs[firstKey]?.results?.[0];
    if (first) return first;
  }
  const r = trainingResults.results;
  if (Array.isArray(r) && r[0]) return r[0];
  return null;
}

export function getAvailableMetricsForScreener(trainingResults: any): string[] {
  const firstResult = getFirstSampleTrainingModel(trainingResults);
  if (!firstResult) return [];
  const problemType = trainingResults.problem_type || 'classification';
  const metrics = getBestMetricsFromHistory(firstResult, problemType);
  if (trainingResults.problem_type === 'regression') {
    const trainTestKeys = ['test_r2', 'train_r2', 'test_mae', 'train_mae', 'test_mse', 'train_mse', 'test_rmse', 'train_rmse'];
    return trainTestKeys.filter((key) => resolveScalarForScreenerFilter(metrics, key) !== undefined);
  }
  const trainTestKeys = [
    'test_accuracy',
    'train_accuracy',
    'accuracy_diff',
    'test_auc',
    'train_auc',
    'auc_diff',
    'test_ks_statistic',
    'train_ks_statistic',
    'ks_statistic_diff',
    'feature_importance_count',
  ];
  return trainTestKeys.filter((key) => {
    if (key === 'accuracy_diff') {
      return (
        getFirstFiniteFromMetrics(metrics, [...TRAIN_ACC_KEYS]) !== undefined &&
        getFirstFiniteFromMetrics(metrics, [...TEST_ACC_KEYS]) !== undefined
      );
    }
    if (key === 'auc_diff') {
      return (
        getFirstFiniteFromMetrics(metrics, [...TRAIN_AUC_KEYS]) !== undefined &&
        getFirstFiniteFromMetrics(metrics, [...TEST_AUC_KEYS]) !== undefined
      );
    }
    if (key === 'ks_statistic_diff') {
      return (
        getFirstFiniteFromMetrics(metrics, [...TRAIN_KS_KEYS]) !== undefined &&
        getFirstFiniteFromMetrics(metrics, [...TEST_KS_KEYS]) !== undefined
      );
    }
    if (key === 'feature_importance_count') return metrics[key] != null;
    return resolveScalarForScreenerFilter(metrics, key) !== undefined;
  });
}

export function getMetricDisplayName(metricKey: string): string {
  const metricMap: Record<string, string> = {
    auc: 'AUC-ROC',
    f1: 'F1-Score',
    precision: 'Precision',
    recall: 'Recall',
    accuracy: 'Accuracy',
    log_loss: 'Log Loss',
    ks_statistic: 'KS Statistic',
    r2: 'R²',
    adjusted_r2: 'Adjusted R²',
    mae: 'MAE',
    mse: 'MSE',
    rmse: 'RMSE',
    train_accuracy: 'Accuracy (Train)',
    train_auc: 'AUC-ROC (Train)',
    train_ks_statistic: 'KS Statistic (Train)',
    test_accuracy: 'Accuracy (Test)',
    test_auc: 'AUC-ROC (Test)',
    test_ks_statistic: 'KS Statistic (Test)',
    train_r2: 'R² (Train)',
    test_r2: 'R² (Test)',
    train_mae: 'MAE (Train)',
    test_mae: 'MAE (Test)',
    train_mse: 'MSE (Train)',
    test_mse: 'MSE (Test)',
    train_rmse: 'RMSE (Train)',
    test_rmse: 'RMSE (Test)',
    accuracy_diff: 'Accuracy Difference (%)',
    auc_diff: 'AUC Difference (%)',
    ks_statistic_diff: 'KS Statistic Difference (%)',
    feature_importance_count: 'Feature Importance Count',
  };
  return metricMap[metricKey] || metricKey.replace(/_/g, ' ').toUpperCase();
}

export const filterOperators: { value: ModelFilterRow['operator']; label: string }[] = [
  { value: '>=', label: 'Greater than or equal (≥)' },
  { value: '<=', label: 'Less than or equal (≤)' },
  { value: '>', label: 'Greater than (>)' },
  { value: '<', label: 'Less than (<)' },
  { value: '==', label: 'Equal to (=)' },
];

export function getManualScreenerModelKey(model: any): string {
  const iterId = model?.is_iteration
    ? model?.iteration_data?.iteration ?? model?.iteration_id ?? 'iter'
    : model?.best_iteration ?? 'best';
  return `${String(model?.segment_id || 'global')}::${String(model?.algorithm || 'algo')}::${String(model?.model_id || 'model')}::${String(iterId)}`;
}

export function getManualScreenerDisplayMetrics(model: any, problemType: string): any {
  if (model?.is_iteration) return model?.metrics || {};
  /** Pruned synthetic rows store final metrics on `metrics` only — never merge iteration_history. */
  if (model?.is_pruned_screener_row && model?.metrics && typeof model.metrics === 'object') {
    return model.metrics;
  }
  return getBestMetricsFromHistory(model, problemType);
}

/**
 * Non-zero feature count for MTA tables. HistGradientBoosting often serializes
 * `feature_importance_count: 0` because sklearn exposes no `feature_importances_`;
 * fall back to `used_features.length` when the stored count is missing or zero.
 *
 * @param trainingBundleUsedFeatures Optional run-level list (auto training often omits
 *   `used_features` on each result row but keeps it on the results bundle).
 */
export function resolveNonzeroFeatureCount(
  model: any,
  metrics: Record<string, any> | null | undefined,
  trainingBundleUsedFeatures?: unknown,
): number | null {
  const m = metrics && typeof metrics === 'object' ? metrics : {};
  const nzRaw = getFirstFiniteFromMetrics(m, ['feature_importance_count']);
  const fromModel = Array.isArray(model?.used_features) ? model.used_features.length : 0;
  const fromBundle = Array.isArray(trainingBundleUsedFeatures) ? trainingBundleUsedFeatures.length : 0;
  const ufLen = fromModel > 0 ? fromModel : fromBundle;
  if (nzRaw !== undefined && nzRaw > 0) {
    return Math.round(Number(nzRaw));
  }
  if (ufLen > 0 && (nzRaw === undefined || nzRaw === 0)) {
    return ufLen;
  }
  if (nzRaw !== undefined && Number.isFinite(Number(nzRaw))) {
    return Math.max(0, Math.round(Number(nzRaw)));
  }
  return ufLen > 0 ? ufLen : null;
}

/**
 * Run-level feature list for display / nz resolution: use bundle `used_features` when
 * present; otherwise segment auto payloads often store `used_features` only on
 * `segment_results.segment_<id>`.
 */
export function resolveTrainingBundleUsedFeatures(
  trainingBundle: any,
  rowSegmentId?: string | null,
): unknown {
  if (!trainingBundle || typeof trainingBundle !== 'object') return undefined;
  if (Array.isArray(trainingBundle.used_features) && trainingBundle.used_features.length > 0) {
    return trainingBundle.used_features;
  }
  const sid = rowSegmentId != null && String(rowSegmentId) !== '' ? String(rowSegmentId) : '';
  if (sid && trainingBundle.segment_results && typeof trainingBundle.segment_results === 'object') {
    const seg = trainingBundle.segment_results[`segment_${sid}`];
    if (Array.isArray(seg?.used_features) && seg.used_features.length > 0) return seg.used_features;
  }
  return undefined;
}

/** Stable fingerprint for the current training result set (global + all segments). */
export function fingerprintMtaTrainingResults(trainingResults: any): string {
  if (!trainingResults) return '';
  try {
    const pool = collectResultsToProcess(trainingResults, 'all');
    const ids = pool.map((m: any) => `${String(m.segment_id ?? 'global')}::${String(m.model_id ?? '')}::${String(m.algorithm ?? '')}`);
    ids.sort();
    return `${pool.length}:${ids.join('>')}`;
  } catch {
    return `err:${trainingResults?.results?.length ?? 0}`;
  }
}

const MTA_SCREENER_DONE_PREFIX = 'model_training_mta_screener_done_v1_';

/** Checkbox shortlist for MTA model screener — read by Model pruning to list the same candidates. */
const MTA_SCREENER_SELECTED_PREFIX = 'model_training_mta_screener_selected_v1_';

function mtaScreenerStorageId(datasetId: string | null | undefined): string {
  return datasetId && String(datasetId).length > 0 ? String(datasetId) : '_midas_session';
}

/** After user confirms the screener shortlist, pruning is unlocked until results change (new fingerprint). */
export function readMtaScreenerPhaseDone(datasetId: string | null | undefined, fingerprint: string): boolean {
  if (!fingerprint) return false;
  try {
    const raw = sessionStorage.getItem(MTA_SCREENER_DONE_PREFIX + mtaScreenerStorageId(datasetId));
    if (!raw) return false;
    const p = JSON.parse(raw);
    return p?.fp === fingerprint;
  } catch {
    return false;
  }
}

export function writeMtaScreenerPhaseDone(datasetId: string | null | undefined, fingerprint: string): void {
  if (!fingerprint) return;
  try {
    sessionStorage.setItem(MTA_SCREENER_DONE_PREFIX + mtaScreenerStorageId(datasetId), JSON.stringify({ fp: fingerprint }));
  } catch {
    /* ignore */
  }
}

/**
 * Persist screener checkbox keys (same fingerprint as training snapshot).
 * `null` from read when missing/stale → pruning shows full candidate pool (legacy).
 */
export function readMtaScreenerSelectedKeys(
  datasetId: string | null | undefined,
  fingerprint: string,
): string[] | null {
  if (!fingerprint) return null;
  try {
    const raw = sessionStorage.getItem(MTA_SCREENER_SELECTED_PREFIX + mtaScreenerStorageId(datasetId));
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (p?.fp !== fingerprint) return null;
    if (!Array.isArray(p.keys)) return null;
    return p.keys.map((k: unknown) => String(k));
  } catch {
    return null;
  }
}

export function writeMtaScreenerSelectedKeys(
  datasetId: string | null | undefined,
  fingerprint: string,
  keys: string[],
): void {
  if (!fingerprint) return;
  try {
    sessionStorage.setItem(
      MTA_SCREENER_SELECTED_PREFIX + mtaScreenerStorageId(datasetId),
      JSON.stringify({ fp: fingerprint, keys }),
    );
  } catch {
    /* ignore */
  }
}

export function clearMtaScreenerSelectedKeys(datasetId: string | null | undefined): void {
  try {
    sessionStorage.removeItem(MTA_SCREENER_SELECTED_PREFIX + mtaScreenerStorageId(datasetId));
  } catch {
    /* ignore */
  }
}

/** Fired after Step 6 writes training JSON to sessionStorage so Step 7 can re-sync (same tab). */
export const MTA_TRAINING_RESULTS_PERSISTED_EVENT = 'midas-mta-training-results-persisted';

export function notifyMtaTrainingResultsPersisted(datasetId: string | null | undefined): void {
  if (typeof window === 'undefined') return;
  try {
    window.dispatchEvent(
      new CustomEvent(MTA_TRAINING_RESULTS_PERSISTED_EVENT, { detail: { datasetId: datasetId ?? null } }),
    );
  } catch {
    /* ignore */
  }
}

function isNonEmptyTrainingPayload(p: any): boolean {
  if (!p || typeof p !== 'object') return false;
  if (Array.isArray(p.results) && p.results.length > 0) return true;
  if (p.segment_results && typeof p.segment_results === 'object' && Object.keys(p.segment_results).length > 0) {
    return true;
  }
  return false;
}

/**
 * SessionStorage key for the MTA UI training snapshot — must match ``getResultsStorageKey`` in
 * ``Step6_5ModelTrainingAgent`` (segment auto uses type ``segment-auto``, not ``auto``).
 */
export function getMtaTrainingResultsStorageKey(
  datasetId: string | null | undefined,
  trainingMode: 'global' | 'segment-specific',
  activeTab: 'auto' | 'manual',
): string | null {
  if (datasetId == null || String(datasetId).length === 0) return null;
  if (trainingMode === 'segment-specific' && activeTab === 'auto') {
    return `model_training_ui_results_${datasetId}_segment-specific_segment-auto`;
  }
  return `model_training_ui_results_${datasetId}_${trainingMode}_${activeTab}`;
}

/**
 * Load persisted training results. When ``trainingMode`` and ``activeTab`` are passed, the
 * matching UI key is tried first so Step 7 matches Step 6 after reload or tab change.
 * Single-arg form scans any stored snapshot for the dataset (fallback for gates / legacy).
 */
export function loadPersistedTrainingResults(
  datasetId: string | null | undefined,
  trainingMode?: 'global' | 'segment-specific',
  activeTab?: 'auto' | 'manual',
): any | null {
  if (datasetId && trainingMode && activeTab) {
    try {
      const primaryKey = getMtaTrainingResultsStorageKey(datasetId, trainingMode, activeTab);
      if (primaryKey) {
        const raw = sessionStorage.getItem(primaryKey);
        if (raw) {
          const p = JSON.parse(raw);
          if (isNonEmptyTrainingPayload(p)) return p;
        }
      }
    } catch {
      /* ignore */
    }
  }

  try {
    const raw = sessionStorage.getItem('training_results');
    if (raw) {
      const p = JSON.parse(raw);
      if (!isNonEmptyTrainingPayload(p)) {
        /* fall through */
      } else if (datasetId && p?.dataset_id != null && String(p.dataset_id) !== String(datasetId)) {
        /* wrong dataset */
      } else {
        return p;
      }
    }
  } catch {
    /* ignore */
  }

  if (!datasetId) return null;

  const preferSegment = (() => {
    try {
      return sessionStorage.getItem(`model_training_mode_${datasetId}`) === 'segment-specific';
    } catch {
      return false;
    }
  })();

  const modeTuples: readonly [string, string][] = preferSegment
    ? [
        ['segment-specific', 'segment-auto'],
        ['segment-specific', 'manual'],
        ['global', 'auto'],
        ['global', 'manual'],
      ]
    : [
        ['global', 'auto'],
        ['global', 'manual'],
        ['segment-specific', 'segment-auto'],
        ['segment-specific', 'manual'],
      ];

  for (const [mode, typ] of modeTuples) {
    try {
      const key = `model_training_ui_results_${datasetId}_${mode}_${typ}`;
      const r = sessionStorage.getItem(key);
      if (!r) continue;
      const p = JSON.parse(r);
      if (isNonEmptyTrainingPayload(p)) return p;
    } catch {
      /* ignore */
    }
  }
  return null;
}

const PRUNED_SCREENER_QUEUE_PREFIX = 'model_pruning_screener_queue_v1_';

/** Pruned models queued from Step 5 pruning — merged into the screener table. */
export function readPrunedScreenerQueue(datasetId: string | null | undefined): any[] {
  if (!datasetId) return [];
  try {
    const raw = sessionStorage.getItem(PRUNED_SCREENER_QUEUE_PREFIX + datasetId);
    if (!raw) return [];
    const p = JSON.parse(raw);
    return Array.isArray(p) ? p : [];
  } catch {
    return [];
  }
}

export function appendPrunedScreenerQueue(datasetId: string | null | undefined, entry: any): void {
  if (!datasetId) return;
  const cur = readPrunedScreenerQueue(datasetId);
  cur.push(entry);
  try {
    sessionStorage.setItem(PRUNED_SCREENER_QUEUE_PREFIX + datasetId, JSON.stringify(cur));
  } catch {
    /* ignore quota */
  }
}

/** Live + session snapshot for ModelBuilder navigation after Model Training (step 4.5). */
export type MtaFlowGate = {
  trainingInProgress: boolean;
  trainingComplete: boolean;
  screenerPhaseDone: boolean;
  variableSelectionConfirmed: boolean;
};

function readVariableSelectionConfirmedAnyMode(datasetId: string): boolean {
  for (const mode of ['global', 'segment-specific'] as const) {
    try {
      const raw = sessionStorage.getItem(`model_training_mta_state_${datasetId}_${mode}`);
      if (raw && JSON.parse(raw)?.variableSelectionConfirmed === true) return true;
    } catch {
      /* ignore */
    }
  }
  return false;
}

/**
 * Read persisted MTA progress for parent navigation (ModelBuilder).
 * Omits `trainingInProgress` — only Step6_5 knows live job state.
 */
export function readMtaNavGateSnapshot(
  datasetId: string | null | undefined,
): Pick<MtaFlowGate, 'trainingComplete' | 'screenerPhaseDone' | 'variableSelectionConfirmed'> {
  if (!datasetId) {
    return { trainingComplete: false, screenerPhaseDone: false, variableSelectionConfirmed: false };
  }
  const variableSelectionConfirmed = readVariableSelectionConfirmedAnyMode(String(datasetId));
  const bundle = loadPersistedTrainingResults(datasetId);
  const hasTraining = isNonEmptyTrainingPayload(bundle);
  const fp = fingerprintMtaTrainingResults(bundle);
  const screenerPhaseDone = readMtaScreenerPhaseDone(datasetId, fp);
  return {
    trainingComplete: hasTraining,
    screenerPhaseDone,
    variableSelectionConfirmed,
  };
}
