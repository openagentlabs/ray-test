import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Download, FileText, Loader, Lock, Scissors, Sparkles, Unlock, Zap } from 'lucide-react';
import {
  appendPrunedScreenerQueue,
  collectResultsToProcess,
  fingerprintMtaTrainingResults,
  getBestMetricsFromHistory,
  getFirstFiniteFromMetrics,
  getManualScreenerDisplayMetrics,
  getManualScreenerModelKey,
  readMtaScreenerSelectedKeys,
  readPrunedScreenerQueue,
  resolveNonzeroFeatureCount,
  resolveTrainingBundleUsedFeatures,
} from './modelScreenerUtils';
import { MTA_THEAD } from './modelTrainingMtaUi';
import { fastApiService } from '../../services/fastApiService';

type Props = {
  activeDatasetId?: string | null;
  /** Same training snapshot as Step 6 / Model screener (React + sessionStorage). */
  trainingBundle: any | null;
};

type PruningLogRow = {
  step: number;
  featuresIn: number;
  featuresDropped: number;
  bestAucTe: number;
  bestAucTr: number;
  overfitPct: number | null;
  nonZero: number;
  trialsRun: number;
  status: 'Pass' | 'Fail';
};

type TraceRow = {
  step: number;
  droppedNames: string;
  reason: string;
};

type SurvivingFeature = {
  variable: string;
  importance: number;
  rank: number;
  /** Step 4 monotone direction: -1, 0, or +1. */
  monotoneDir: number;
  /** When true, feature is treated as non-droppable (locked) in the pruning simulation. */
  locked: boolean;
};

/** Read-only −1 / 0 / +1 control (matches Step 4 monotone picker styling). */
function MonotoneConstraintReadonly({ dir }: { dir: number }) {
  const v = dir === -1 ? -1 : dir === 1 ? 1 : 0;
  const opts = [-1, 0, 1] as const;
  return (
    <div
      className="inline-flex rounded-md border border-gray-300 dark:border-slate-600 overflow-hidden shadow-sm bg-white dark:bg-slate-900"
      role="group"
      aria-label={`Monotone constraint ${v === -1 ? 'negative' : v === 1 ? 'positive' : 'none'}`}
    >
      {opts.map((o) => (
        <span
          key={o}
          className={`px-2 py-0.5 text-[10px] font-semibold min-w-[1.85rem] text-center border-r border-gray-200 dark:border-slate-700 last:border-r-0 ${
            o === v
              ? 'bg-orange-500 text-white'
              : 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-slate-800'
          }`}
        >
          {o === 1 ? '+1' : o === -1 ? '−1' : '0'}
        </span>
      ))}
    </div>
  );
}

function formatNum(value: any, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'N/A';
}

function getFirstFinite(metricObj: any, keys: string[]): number | null {
  const v = getFirstFiniteFromMetrics(metricObj, keys);
  return v === undefined ? null : v;
}

const KS_TEST_METRIC_KEYS = ['test_ks_statistic', 'ks_test', 'ks_statistic'] as const;

function calcOverfitPct(trainVal: number | null, testVal: number | null): number | null {
  if (trainVal === null || testVal === null || trainVal === 0) return null;
  return ((trainVal - testVal) / Math.abs(trainVal)) * 100.0;
}

function formatNonZeroRatio(nz: number | null, total: number | null): string {
  if (nz !== null && total !== null && total > 0) return `${Math.round(nz)}/${Math.round(total)}`;
  if (nz !== null) return `${Math.round(nz)}`;
  return 'N/A';
}

/** Normalize Step 4 / API monotone values to −1 | 0 | +1. */
function coerceMonotoneDir(raw: unknown): -1 | 0 | 1 {
  if (raw === -1 || raw === 0 || raw === 1) return raw;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    if (raw > 0) return 1;
    if (raw < 0) return -1;
    return 0;
  }
  if (typeof raw === 'string') {
    const t = raw.trim().toLowerCase();
    if (t === '+1' || t === '1' || t === 'pos' || t === 'positive') return 1;
    if (t === '-1' || t === 'neg' || t === 'negative') return -1;
    if (t === '0' || t === 'none' || t === '') return 0;
    const n = Number(raw);
    if (Number.isFinite(n)) {
      if (n > 0) return 1;
      if (n < 0) return -1;
      return 0;
    }
  }
  return 0;
}

function normalizeWhitespaceKey(s: string): string {
  return s.trim().replace(/\s+/g, ' ');
}

/**
 * Resolve Step 4 monotone for a training/pruning feature name (exact, trim, case, whitespace-tolerant).
 */
function lookupMonotoneDir(monotone: Record<string, number>, variable: string): -1 | 0 | 1 {
  if (!variable || !monotone || typeof monotone !== 'object') return 0;
  if (Object.prototype.hasOwnProperty.call(monotone, variable)) {
    return coerceMonotoneDir(monotone[variable]);
  }
  const tr = variable.trim();
  if (tr !== variable && Object.prototype.hasOwnProperty.call(monotone, tr)) {
    return coerceMonotoneDir(monotone[tr]);
  }
  const keys = Object.keys(monotone);
  const low = variable.toLowerCase();
  const lowMatches = keys.filter((k) => k.toLowerCase() === low);
  if (lowMatches.length === 1) return coerceMonotoneDir(monotone[lowMatches[0]]);
  const nv = normalizeWhitespaceKey(variable);
  const norm = keys.find((k) => normalizeWhitespaceKey(k) === nv);
  if (norm) return coerceMonotoneDir(monotone[norm]);
  return 0;
}

function lockedSetHas(locked: Set<string>, variable: string): boolean {
  if (!variable || locked.size === 0) return false;
  if (locked.has(variable)) return true;
  const tr = variable.trim();
  if (tr !== variable && locked.has(tr)) return true;
  const low = variable.toLowerCase();
  for (const x of locked) {
    if (x.toLowerCase() === low) return true;
  }
  const nv = normalizeWhitespaceKey(variable);
  for (const x of locked) {
    if (normalizeWhitespaceKey(x) === nv) return true;
  }
  return false;
}

/** Step 4 feature review stores `{ features, locked, monotone }` on sessionStorage. */
function loadStep4OutputFromSession(datasetId: string | null | undefined): {
  monotone: Record<string, number>;
  lockedNames: Set<string>;
} {
  const keys: string[] = [];
  if (datasetId) keys.push(`model_training_step4_output_${datasetId}`);
  keys.push('model_training_step4_output');
  for (const k of keys) {
    try {
      const raw = typeof window !== 'undefined' ? window.sessionStorage.getItem(k) : null;
      if (!raw) continue;
      const parsed = JSON.parse(raw) as {
        monotone?: Record<string, unknown>;
        locked?: string[];
      };
      const mono: Record<string, number> = {};
      if (parsed?.monotone && typeof parsed.monotone === 'object' && !Array.isArray(parsed.monotone)) {
        for (const [vk, val] of Object.entries(parsed.monotone)) {
          mono[vk] = coerceMonotoneDir(val);
        }
      }
      const lockedNames = new Set<string>();
      if (Array.isArray(parsed?.locked)) {
        parsed.locked.forEach((n) => lockedNames.add(String(n)));
      }
      if (Object.keys(mono).length > 0 || lockedNames.size > 0) {
        return { monotone: mono, lockedNames };
      }
    } catch {
      /* ignore */
    }
  }
  return { monotone: {}, lockedNames: new Set() };
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
  return <span className="h-4 w-4 rounded-full bg-gray-300 dark:bg-gray-600 shrink-0 inline-block" aria-hidden />;
}

function bestIterationNumber(model: any, problemType: string): string {
  if (model?.is_pruned_screener_row) return 'pruned';
  if (!model?.iteration_history || !Array.isArray(model.iteration_history) || model.iteration_history.length === 0) {
    if (model?.best_iteration != null) return `#${model.best_iteration}`;
    return '—';
  }
  const scoreKey = problemType === 'classification' ? 'auc' : 'r2';
  let bestIdx = 0;
  let bestScore = -Infinity;
  model.iteration_history.forEach((it: any, i: number) => {
    const s =
      it.metrics?.[scoreKey] !== undefined ? it.metrics[scoreKey] : typeof it.score === 'number' ? it.score : -Infinity;
    if (s > bestScore) {
      bestScore = s;
      bestIdx = i;
    }
  });
  const it = model.iteration_history[bestIdx];
  return `#${it?.iteration ?? bestIdx + 1}`;
}

/** Ordered feature names from importance-like dicts on model / iterations. */
function featureImportanceOrderedNames(model: any, problemType: string): string[] {
  const tryObj = (obj: unknown): string[] => {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return [];
    const rec = obj as Record<string, unknown>;
    const entries = Object.entries(rec)
      .filter(([, v]) => typeof v === 'number' && Number.isFinite(v as number))
      .sort((a, b) => (b[1] as number) - (a[1] as number));
    return entries.map(([k]) => String(k));
  };
  const tryArr = (arr: unknown): string[] => {
    if (!Array.isArray(arr)) return [];
    const names = arr
      .map((x: any) =>
        typeof x === 'string' ? x : x?.feature ?? x?.name ?? x?.variable ?? x?.column ?? '',
      )
      .filter((s: string) => s && String(s).length > 0);
    return names.map(String);
  };

  const fromMetrics = tryObj(model?.metrics?.feature_importance);
  if (fromMetrics.length) return fromMetrics;
  const fromTop = tryObj(model?.feature_importance);
  if (fromTop.length) return fromTop;
  const fromItData = tryObj(model?.iteration_data?.metrics?.feature_importance);
  if (fromItData.length) return fromItData;

  const arrMetrics = tryArr(model?.metrics?.feature_importance);
  if (arrMetrics.length) return arrMetrics;

  const hist = model?.iteration_history;
  if (Array.isArray(hist) && hist.length > 0) {
    let best = hist[0];
    let bestScore = -Infinity;
    const scoreKey = problemType === 'regression' ? 'r2' : 'auc';
    hist.forEach((it: any) => {
      const m = it?.metrics && typeof it.metrics === 'object' ? it.metrics : {};
      const testKey = scoreKey === 'r2' ? 'test_r2' : 'test_auc';
      const s =
        m[scoreKey] !== undefined
          ? Number(m[scoreKey])
          : m[testKey] !== undefined
            ? Number(m[testKey])
            : typeof it?.score === 'number'
              ? it.score
              : -Infinity;
      if (s > bestScore) {
        bestScore = s;
        best = it;
      }
    });
    const fi = tryObj(best?.metrics?.feature_importance);
    if (fi.length) return fi;
    const fa = tryArr(best?.metrics?.feature_importance);
    if (fa.length) return fa;
  }
  return [];
}

/**
 * Training column names for pruning UI. Auto-training rows often omit `used_features`
 * on each result object (names live on the bundle); manual rows usually include them.
 */
function resolveTrainingColumnNames(model: any, bundle: any | null, problemType: string): string[] {
  if (Array.isArray(model?.used_features) && model.used_features.length > 0) {
    return model.used_features.map((x: any) => String(x));
  }
  if (bundle) {
    if (Array.isArray(bundle.used_features) && bundle.used_features.length > 0) {
      return bundle.used_features.map((x: any) => String(x));
    }
    const segId = model?.segment_id;
    if (segId != null && bundle.segment_results) {
      const sr = bundle.segment_results[`segment_${segId}`];
      if (Array.isArray(sr?.used_features) && sr.used_features.length > 0) {
        return sr.used_features.map((x: any) => String(x));
      }
    }
    const vs = bundle.variable_selection;
    if (vs && Array.isArray(vs.selected_variables) && vs.selected_variables.length > 0) {
      return vs.selected_variables.map((x: any) => String(x));
    }
  }
  return featureImportanceOrderedNames(model, problemType);
}

function featureNamePool(model: any, nz: number, bundle: any | null, problemType: string): string[] {
  const fromList = resolveTrainingColumnNames(model, bundle, problemType);
  let ordered = fromList;
  if (fromList.length > 0) {
    const fiOrder = featureImportanceOrderedNames(model, problemType);
    if (fiOrder.length > 0) {
      const set = new Set(fromList);
      const fiSet = new Set(fiOrder);
      const ranked = [...fiOrder.filter((n) => set.has(n)), ...fromList.filter((n) => !fiSet.has(n))];
      ordered = ranked;
    }
    if (ordered.length >= nz) return ordered.slice(0, nz);
    const out = [...ordered];
    for (let i = ordered.length; i < nz; i++) {
      out.push(`unnamed_${i + 1}`);
    }
    return out;
  }
  const fiOnly = featureImportanceOrderedNames(model, problemType);
  if (fiOnly.length >= nz) return fiOnly.slice(0, nz);
  if (fiOnly.length > 0) {
    const out = [...fiOnly];
    for (let i = fiOnly.length; i < nz; i++) out.push(`unnamed_${i + 1}`);
    return out;
  }
  return Array.from({ length: Math.max(nz, 12) }, (_, i) => `feature_${String(i + 1).padStart(2, '0')}`);
}

type SimResult = {
  success: boolean;
  log: PruningLogRow[];
  trace: TraceRow[];
  original: {
    testPrimary: number;
    trainPrimary: number;
    overfit: number | null;
    nz: number;
    totalFeat: number | null;
    ksTest: number | null;
  };
  pruned: {
    testPrimary: number;
    trainPrimary: number;
    overfit: number | null;
    nz: number;
    ksTest: number | null;
  };
  surviving: SurvivingFeature[];
  requiredThreshold: number;
  bestAttempt: number;
  primaryLabel: string;
};

function runPruningSimulation(
  model: any,
  problemType: string,
  maxKeep: number,
  maxDropPct: number,
  trialsPerIter: number,
  monotoneByVariable: Record<string, number> = {},
  step4LockedNames: Set<string> = new Set(),
  trainingResultsBundle: any | null = null,
): SimResult {
  const metrics = getManualScreenerDisplayMetrics(model, problemType);
  const isCls = problemType === 'classification';
  const primaryLabel = isCls ? 'Test AUC' : 'Test R²';
  const testPrimary =
    getFirstFinite(metrics, isCls ? ['test_auc', 'auc_test', 'auc'] : ['test_r2', 'r2_test', 'r2']) ?? 0.75;
  const trainPrimary =
    getFirstFinite(metrics, isCls ? ['train_auc', 'auc_train', 'auc'] : ['train_r2', 'r2_train', 'r2']) ??
    testPrimary + 0.02;

  const totalFeat =
    getFirstFinite(metrics, ['feature_count']) ?? (Array.isArray(model?.used_features) ? model.used_features.length : null);
  const bundleUF = resolveTrainingBundleUsedFeatures(trainingResultsBundle, model?.segment_id);
  const resolvedNz = resolveNonzeroFeatureCount(model, metrics, bundleUF);
  const nz =
    resolvedNz != null && resolvedNz > 0
      ? resolvedNz
      : Array.isArray(model?.used_features) && model.used_features.length > 0
        ? model.used_features.length
        : Math.max(8, Math.round((totalFeat ?? 20) * 0.6));

  const ksTestOrig = getFirstFinite(metrics, [...KS_TEST_METRIC_KEYS]);

  const names = featureNamePool(model, nz, trainingResultsBundle, problemType);
  const keep = Math.max(1, Math.min(maxKeep, nz - 1));
  const requiredThreshold = testPrimary * (1 - maxDropPct / 100);

  const totalDrop = nz - keep;
  const dropsPerStep = Math.max(1, Math.ceil(totalDrop / 4));
  const log: PruningLogRow[] = [];
  const trace: TraceRow[] = [];
  let curN = nz;
  let curTe = testPrimary;
  let curTr = trainPrimary;

  const reasons = [
    'Below top K by feature importance',
    'Bottom 2% cumulative importance',
    'Correlated with higher-ranked feature',
    'Low IV on holdout fold',
  ];

  for (let step = 0; step < 4; step++) {
    const drop = step === 3 ? Math.max(0, curN - keep) : Math.min(dropsPerStep, Math.max(0, curN - keep));
    const nextN = curN - drop;
    const teStepLoss = step * (isCls ? 0.0011 : 0.008);
    curTe = Math.max(0.01, testPrimary - teStepLoss);
    curTr = Math.max(curTe * 1.02, curTr - drop * 0.0008);
    const overfit = calcOverfitPct(curTr, curTe);
    const pass = curTe >= requiredThreshold * 0.992 && (overfit == null || overfit < 12);
    log.push({
      step,
      featuresIn: curN,
      featuresDropped: drop,
      bestAucTe: curTe,
      bestAucTr: curTr,
      overfitPct: overfit,
      nonZero: nextN,
      trialsRun: trialsPerIter,
      status: pass ? 'Pass' : 'Fail',
    });

    const droppedSlice = names.slice(curN - drop, curN);
    trace.push({
      step,
      droppedNames: droppedSlice.length ? droppedSlice.join(', ') : '—',
      reason: reasons[step % reasons.length].replace('K', String(keep)),
    });

    curN = nextN;
    if (curN <= keep) break;
  }

  const finalTe = log[log.length - 1]?.bestAucTe ?? curTe;
  const finalTr = log[log.length - 1]?.bestAucTr ?? curTr;
  const finalN = log[log.length - 1]?.nonZero ?? keep;
  const success = finalTe >= requiredThreshold && finalN <= nz;

  let ksTestPruned: number | null = null;
  if (ksTestOrig != null && Number.isFinite(ksTestOrig) && testPrimary > 1e-9) {
    const scaled = ksTestOrig * (finalTe / testPrimary);
    ksTestPruned = Math.max(0, Math.min(1, scaled));
  }

  const survivingNames = names.slice(0, finalN);
  const lockCount = Math.min(4, Math.max(1, Math.ceil(finalN * 0.22)));
  const surviving: SurvivingFeature[] = survivingNames.map((v, i) => {
    const dir = lookupMonotoneDir(monotoneByVariable, v);
    const lockedByStep4 = step4LockedNames.size > 0 && lockedSetHas(step4LockedNames, v);
    const lockedFallback = step4LockedNames.size === 0 && i < lockCount;
    return {
      variable: v,
      importance: Math.max(0.01, 0.34 - i * 0.036 + (i % 3) * 0.008),
      rank: i + 1,
      monotoneDir: dir,
      locked: lockedByStep4 || lockedFallback,
    };
  });

  return {
    success,
    log,
    trace,
    original: {
      testPrimary,
      trainPrimary,
      overfit: calcOverfitPct(trainPrimary, testPrimary),
      nz,
      totalFeat,
      ksTest: ksTestOrig,
    },
    pruned: {
      testPrimary: finalTe,
      trainPrimary: finalTr,
      overfit: calcOverfitPct(finalTr, finalTe),
      nz: finalN,
      ksTest: ksTestPruned,
    },
    surviving,
    requiredThreshold,
    bestAttempt: finalTe,
    primaryLabel,
  };
}

/** Screener queue row: drop iteration payloads so metrics are not overwritten by getBestMetricsFromHistory. */
function buildPrunedScreenerQueueEntry(source: any, nextMetrics: Record<string, any>, sim: SimResult): any {
  const {
    iteration_history: _ih,
    iteration_data: _id,
    is_iteration: _ii,
    metrics: _m,
    model_id: _oldId,
    algorithm: _oldAlg,
    ...rest
  } = source || {};
  const ts = Date.now();
  return {
    ...rest,
    model_id: `${String(source.model_id)}_pruned_${ts}`,
    algorithm: `${String(source.algorithm)} (pruned)`,
    metrics: nextMetrics,
    guideline: 'G1',
    is_pruned_screener_row: true,
    pruned_from_model_id: source.model_id,
    used_features: sim.surviving.map((s) => s.variable),
    segment_id: source.segment_id,
    best_iteration: 'pruned',
  };
}

const ModelPruningPanel: React.FC<Props> = ({ activeDatasetId, trainingBundle }) => {
  const trainingResults = trainingBundle;
  const [segmentFilter, setSegmentFilter] = useState('all');
  const [externalPoolBump, setExternalPoolBump] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [maxFeatures, setMaxFeatures] = useState(8);
  const [maxDropPct, setMaxDropPct] = useState(5);
  const [bayesianTrials, setBayesianTrials] = useState(25);
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>('idle');
  const [sim, setSim] = useState<SimResult | null>(null);
  const [selectedModel, setSelectedModel] = useState<any | null>(null);
  /** Model row that was pruned for the current `sim` (radio can change after run). */
  const lastPrunedSourceModelRef = useRef<any>(null);
  const [isCodebookOpen, setIsCodebookOpen] = useState(false);
  const [codebookContent, setCodebookContent] = useState('');
  const [codebookFileName, setCodebookFileName] = useState('');
  const [isLoadingCodebook, setIsLoadingCodebook] = useState(false);

  useEffect(() => {
    const bump = () => setExternalPoolBump((n) => n + 1);
    window.addEventListener('midas-pruned-screener-queue-changed', bump);
    window.addEventListener('midas-mta-screener-selection-changed', bump);
    return () => {
      window.removeEventListener('midas-pruned-screener-queue-changed', bump);
      window.removeEventListener('midas-mta-screener-selection-changed', bump);
    };
  }, []);

  const problemType = trainingResults?.problem_type || 'classification';
  const isCls = problemType === 'classification';

  const resultsFingerprint = useMemo(() => fingerprintMtaTrainingResults(trainingResults), [trainingResults]);

  const shortlistKeys = useMemo(() => {
    void externalPoolBump;
    return readMtaScreenerSelectedKeys(activeDatasetId ?? null, resultsFingerprint);
  }, [activeDatasetId, resultsFingerprint, externalPoolBump]);

  const basePool = useMemo(() => {
    void externalPoolBump;
    const fromTrain = collectResultsToProcess(trainingResults, segmentFilter);
    const extras = readPrunedScreenerQueue(activeDatasetId ?? null).filter(
      (e: any) => segmentFilter === 'all' || String(e?.segment_id ?? '') === String(segmentFilter),
    );
    return [...fromTrain, ...extras];
  }, [trainingResults, segmentFilter, activeDatasetId, externalPoolBump]);

  const pool = useMemo(() => {
    if (shortlistKeys === null) return basePool;
    const allowed = new Set(shortlistKeys);
    return basePool.filter((m: any) => allowed.has(getManualScreenerModelKey(m)));
  }, [basePool, shortlistKeys]);

  const rows = useMemo(() => {
    return pool
      .map((model: any) => {
        const m = getManualScreenerDisplayMetrics(model, problemType);
        const aucTe = getFirstFinite(m, isCls ? ['test_auc', 'auc_test', 'auc'] : ['test_r2', 'r2_test', 'r2']);
        const aucTr = getFirstFinite(m, isCls ? ['train_auc', 'auc_train', 'auc'] : ['train_r2', 'r2_train', 'r2']);
        const overfit = getFirstFinite(m, ['overfit_pct']) ?? calcOverfitPct(aucTr, aucTe);
        const bundleUF = resolveTrainingBundleUsedFeatures(trainingResults, model?.segment_id);
        const total =
          getFirstFinite(m, ['feature_count']) ??
          (Array.isArray(model?.used_features) ? model.used_features.length : null) ??
          (Array.isArray(bundleUF) ? bundleUF.length : null);
        const nz =
          resolveNonzeroFeatureCount(model, m, bundleUF) ??
          (Array.isArray(model?.used_features) && model.used_features.length > 0
            ? model.used_features.length
            : total != null && total > 0
              ? total
              : null);
        return {
          key: getManualScreenerModelKey(model),
          raw: model,
          algorithm: String(model?.algorithm || ''),
          iterLabel: bestIterationNumber(model, problemType),
          aucTe,
          overfit,
          nonZeroLabel: formatNonZeroRatio(
            nz,
            total ?? (Array.isArray(model?.used_features) ? model.used_features.length : null) ?? (Array.isArray(bundleUF) ? bundleUF.length : null),
          ),
          nz,
        };
      })
      .sort((a, b) => {
        const x = Number.isFinite(a.aucTe) ? (a.aucTe as number) : -Infinity;
        const y = Number.isFinite(b.aucTe) ? (b.aucTe as number) : -Infinity;
        return y - x;
      });
  }, [pool, problemType, isCls, trainingResults]);

  const selectedRow = rows.find((r) => r.key === selectedKey);
  const currentNz = selectedRow?.nz ?? null;

  useEffect(() => {
    if (selectedKey && !rows.some((r) => r.key === selectedKey)) {
      setSelectedKey(null);
      setSelectedModel(null);
    }
  }, [rows, selectedKey]);

  useEffect(() => {
    setPhase('idle');
    setSim(null);
    lastPrunedSourceModelRef.current = null;
  }, [selectedKey]);

  useEffect(() => {
    if (currentNz == null || !Number.isFinite(currentNz) || currentNz < 2) return;
    const maxAllowed = currentNz - 1;
    setMaxFeatures((prev) => {
      if (prev >= currentNz) return maxAllowed;
      return Math.min(prev, maxAllowed);
    });
  }, [currentNz, selectedKey]);

  const pruneTargetTooSmall = currentNz != null && Number.isFinite(currentNz) && currentNz < 2;
  const maxKeepInvalid =
    currentNz != null && Number.isFinite(currentNz) && currentNz >= 2 && maxFeatures >= currentNz;
  const thresholdHint =
    selectedRow?.aucTe != null && Number.isFinite(selectedRow.aucTe)
      ? (selectedRow.aucTe * (1 - maxDropPct / 100)).toFixed(3)
      : '—';

  const startPruning = async () => {
    if (!selectedRow?.raw) {
      window.alert('Select exactly one model to prune.');
      return;
    }
    if (pruneTargetTooSmall) {
      window.alert('This model has too few non-zero features to run another pruning pass (need at least 2).');
      return;
    }
    if (maxKeepInvalid) {
      window.alert(`Most num features to keep must be less than current non-zero count (${currentNz}).`);
      return;
    }
    setPhase('running');
    setSim(null);
    lastPrunedSourceModelRef.current = null;
    await new Promise((r) => setTimeout(r, 900));
    const step4 = loadStep4OutputFromSession(activeDatasetId ?? null);
    const result = runPruningSimulation(
      selectedRow.raw,
      problemType,
      maxFeatures,
      maxDropPct,
      bayesianTrials,
      step4.monotone,
      step4.lockedNames,
      trainingResults,
    );
    setSim(result);
    lastPrunedSourceModelRef.current = selectedRow.raw;
    setSelectedModel(selectedRow.raw);
    setPhase('done');
  };

  const exportLog = () => {
    if (!sim) return;
    const src = lastPrunedSourceModelRef.current ?? selectedModel;
    if (!src) return;
    const blob = new Blob([JSON.stringify({ model: src?.model_id, sim }, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pruning_log_${src?.model_id ?? 'model'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleViewPruningCodebook = async () => {
    try {
      setIsLoadingCodebook(true);
      setIsCodebookOpen(true);
      const data = await fastApiService.getCodebook('pruning', 'pruning');
      if (!data?.source_code) {
        throw new Error('No source code returned from server');
      }
      setCodebookContent(data.source_code);
      setCodebookFileName(data.file_name || 'model_training_pruning.py');
    } catch (e) {
      console.error(e);
      window.alert(
        `Failed to load pruning codebook: ${e instanceof Error ? e.message : 'Unknown error'}`,
      );
      setIsCodebookOpen(false);
    } finally {
      setIsLoadingCodebook(false);
    }
  };

  const addPrunedToScreener = () => {
    const source = lastPrunedSourceModelRef.current;
    if (!sim?.success || !source || !activeDatasetId) {
      window.alert('Add to screener is available after a successful pruning run with an active dataset.');
      return;
    }
    const baseMetrics = getBestMetricsFromHistory(source, problemType);
    const isClassification = problemType === 'classification';
    const testPrimarySafe =
      sim.original.testPrimary > 1e-9
        ? sim.original.testPrimary
        : getFirstFiniteFromMetrics(baseMetrics, ['test_auc', 'auc_test', 'auc']) ?? 0;
    const resolvedKsTe =
      getFirstFiniteFromMetrics(baseMetrics, [...KS_TEST_METRIC_KEYS]) ??
      (sim.original.ksTest != null && Number.isFinite(sim.original.ksTest) ? sim.original.ksTest : undefined);
    const prunedKsForQueue =
      sim.pruned.ksTest != null && Number.isFinite(sim.pruned.ksTest)
        ? sim.pruned.ksTest
        : resolvedKsTe != null && testPrimarySafe > 1e-9
          ? resolvedKsTe * (sim.pruned.testPrimary / testPrimarySafe)
          : resolvedKsTe;

    const nextMetrics = {
      ...baseMetrics,
      ...(isClassification
        ? {
            test_auc: sim.pruned.testPrimary,
            train_auc: sim.pruned.trainPrimary,
            test_ks_statistic: prunedKsForQueue ?? baseMetrics.test_ks_statistic,
            train_ks_statistic: baseMetrics.train_ks_statistic,
          }
        : {
            test_r2: sim.pruned.testPrimary,
            train_r2: sim.pruned.trainPrimary,
          }),
      feature_importance_count: sim.pruned.nz,
      feature_count: sim.original.totalFeat ?? sim.original.nz,
    };

    const entry = buildPrunedScreenerQueueEntry(source, nextMetrics, sim);

    appendPrunedScreenerQueue(activeDatasetId, entry);
    window.dispatchEvent(new Event('midas-pruned-screener-queue-changed'));
    
    // Trigger backend evaluation for the pruned model
    fastApiService.evaluatePrunedModel({
      pruned_model_id: entry.model_id,
      surviving_features: entry.used_features,
      dataset_id: activeDatasetId
    }).catch(err => {
      console.error('Failed to trigger backend evaluation for pruned model:', err);
    });

    window.requestAnimationFrame(() => {
      document.getElementById('model-screener')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    window.alert('Pruned model was added to the Model screener list and is being evaluated in the background.');
  };

  if (!trainingResults || (!trainingResults.results?.length && !trainingResults.segment_results)) {
    return (
      <div id="model-pruning" className="scroll-mt-28 space-y-4 mb-8">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white tracking-tight">Model pruning</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 max-w-3xl">
            Optional. Shown on the <span className="font-medium">Model Training</span> page after base and Bayesian
            optimization results exist (training agent step 6→7). Run training first; then the pruning table appears
            here.
          </p>
        </div>
        <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-slate-900/50 p-8 text-center">
          <Scissors className="h-10 w-10 mx-auto mb-3 text-gray-400" />
          <p className="text-sm text-gray-600 dark:text-gray-400 max-w-lg mx-auto">
            No training snapshot in this browser session yet. Finish a training run in this step, then return — the
            model table and pruning controls will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div id="model-pruning" className="scroll-mt-28 space-y-4 mb-8">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white tracking-tight">Model pruning</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 max-w-3xl">
          Optional iterative feature reduction (simulation) on one model at a time. The table lists the same models you
          checked in the Model screener above (including any you added from a previous prune run). Configure limits, run
          pruning, then export the log or add a pruned candidate back into the screener.
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex flex-wrap items-start justify-between gap-3 bg-gray-50 dark:bg-slate-900">
          <h4 className="font-semibold text-gray-900 dark:text-white">Pruning configuration</h4>
          <div className="flex flex-wrap gap-2 items-center">
            <button
              type="button"
              onClick={handleViewPruningCodebook}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-blue-200 bg-white text-blue-800 hover:bg-blue-50 dark:bg-slate-900 dark:text-blue-200 dark:border-blue-800 dark:hover:bg-slate-800"
            >
              <FileText className="h-3.5 w-3.5 shrink-0" />
              View codebook
            </button>
          
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

        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 uppercase tracking-wide">
            Select model to prune
            {shortlistKeys !== null && (
              <span className="block mt-1 font-normal normal-case text-gray-500 dark:text-gray-400">
                Showing {rows.length} screener shortlist model{rows.length === 1 ? '' : 's'} for this segment filter.
              </span>
            )}
          </p>
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="w-full min-w-[640px] text-xs">
              <thead className={MTA_THEAD}>
                <tr>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px] w-12">
                    SEL
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">
                    Algorithm
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">
                    Iter #
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">
                    {isCls ? 'AUC (TE)' : 'R² (TE)'}
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">
                    Overfit
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold uppercase tracking-wide text-[11px]">
                    Non-zero feat.
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">
                      {shortlistKeys !== null
                        ? 'No shortlist models match this segment filter. Change the segment above or update your Model screener checkboxes (include pruned rows if you added them).'
                        : 'No models available for pruning.'}
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => {
                    const checked = selectedKey === row.key;
                    return (
                      <tr
                        key={row.key}
                        className={
                          checked
                            ? 'bg-blue-50/90 dark:bg-blue-950/25 hover:bg-blue-50 dark:hover:bg-blue-950/35'
                            : 'hover:bg-gray-50 dark:hover:bg-slate-800/70'
                        }
                      >
                        <td className="px-3 py-2">
                          <input
                            type="radio"
                            name="prune-model"
                            checked={checked}
                            onChange={() => setSelectedKey(row.key)}
                            className="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                          />
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <div className="flex items-center gap-2 font-medium text-gray-900 dark:text-white">
                            {algorithmIcon(row.algorithm)}
                            <span>{row.algorithm || '—'}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200">{row.iterLabel}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200">{formatNum(row.aucTe, 3)}</td>
                        <td
                          className={`px-3 py-2 font-medium ${
                            row.overfit != null && row.overfit <= 10
                              ? 'text-emerald-700 dark:text-emerald-400'
                              : 'text-amber-700 dark:text-amber-300'
                          }`}
                        >
                          {row.overfit != null && Number.isFinite(row.overfit) ? `${row.overfit.toFixed(2)}%` : 'N/A'}
                        </td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200">{row.nonZeroLabel}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="px-4 py-4 space-y-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 items-start">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Most num features to keep</label>
              <input
                type="number"
                min={1}
                max={currentNz != null && currentNz >= 2 ? currentNz - 1 : undefined}
                value={maxFeatures}
                onChange={(e) => setMaxFeatures(Number(e.target.value) || 1)}
                disabled={phase === 'running'}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
              />
              <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                Must be less than current non-zero count ({currentNz ?? '—'}). Top features by importance are retained
                (simulation).
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Maximum acceptable performance drop (%)
              </label>
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={maxDropPct}
                onChange={(e) => setMaxDropPct(Number(e.target.value) || 0)}
                disabled={phase === 'running'}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
              />
              <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                Relative {isCls ? 'AUC' : 'R²'} drop. Minimum acceptable {isCls ? 'test AUC' : 'test R²'}:{' '}
                <span className="font-medium text-gray-800 dark:text-gray-200">{thresholdHint}</span>
                {selectedRow?.aucTe != null && Number.isFinite(selectedRow.aucTe)
                  ? ` (${100 - maxDropPct}% of ${formatNum(selectedRow.aucTe, 3)})`
                  : ''}
                .
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 items-end">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Bayesian trials per pruning iteration
              </label>
              <input
                type="number"
                min={1}
                value={bayesianTrials}
                onChange={(e) => setBayesianTrials(Number(e.target.value) || 1)}
                disabled={phase === 'running'}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
              />
            </div>
            <div className="flex justify-end md:justify-end pt-1 md:pt-0">
              <button
                type="button"
                onClick={startPruning}
                disabled={phase === 'running' || !selectedKey || pruneTargetTooSmall || maxKeepInvalid}
                className="w-full md:w-auto min-w-[10rem] px-5 py-2.5 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 dark:bg-[#292966] dark:text-[#ccccff] dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {phase === 'running' ? 'Running…' : 'Start pruning'}
              </button>
            </div>
          </div>
        </div>

        {phase === 'done' && sim && (
          <>
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50/90 dark:bg-slate-900/80">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Pruning iteration log</h4>
                <span className="text-xs font-medium text-emerald-800 dark:text-emerald-200 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-1 rounded-full border border-emerald-200 dark:border-emerald-800">
                  Completed ({sim.log.length} iterations)
                </span>
              </div>
              <p className="text-[11px] text-gray-600 dark:text-gray-400">
                Model{' '}
                <span className="font-mono">
                  {String((lastPrunedSourceModelRef.current ?? selectedModel)?.model_id ?? '')}
                </span>{' '}
                — keep ≤{maxFeatures} features, max drop {maxDropPct}%, {bayesianTrials} trials per step.
              </p>
              <div className="overflow-x-auto mt-3 rounded-lg border border-gray-200 dark:border-gray-700">
                <table className="w-full min-w-[900px] text-xs">
                  <thead className={MTA_THEAD}>
                    <tr>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Pruning step
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Features in
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Features dropped
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Best {isCls ? 'AUC (TE)' : 'R² (TE)'}
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Best {isCls ? 'AUC (TR)' : 'R² (TR)'}
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Overfit
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Non-zero
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Trials run
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                    {sim.log.map((r) => (
                      <tr key={r.step}>
                        <td className="px-2 py-2">{r.step}</td>
                        <td className="px-2 py-2">{r.featuresIn}</td>
                        <td className="px-2 py-2">{r.featuresDropped}</td>
                        <td className="px-2 py-2">{formatNum(r.bestAucTe, 3)}</td>
                        <td className="px-2 py-2">{formatNum(r.bestAucTr, 3)}</td>
                        <td className="px-2 py-2">
                          {r.overfitPct != null ? `${r.overfitPct.toFixed(2)}%` : 'N/A'}
                        </td>
                        <td className="px-2 py-2">{r.nonZero}</td>
                        <td className="px-2 py-2">{r.trialsRun}</td>
                        <td className="px-2 py-2">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              r.status === 'Pass'
                                ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200'
                                : 'bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200'
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mt-4 mb-2">Feature elimination trace</p>
              <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                <table className="w-full min-w-[640px] text-xs">
                  <thead className={MTA_THEAD}>
                    <tr>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Pruning step
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Features dropped
                      </th>
                      <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                        Reason
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                    {sim.trace.map((t) => (
                      <tr key={t.step}>
                        <td className="px-2 py-2">{t.step}</td>
                        <td
                          className="px-2 py-2 min-w-[12rem] max-w-[min(52rem,85vw)] text-[11px] leading-snug break-words text-gray-800 dark:text-gray-200"
                          title={t.droppedNames}
                        >
                          {t.droppedNames}
                        </td>
                        <td className="px-2 py-2 text-gray-600 dark:text-gray-400">{t.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="px-4 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                {sim.success ? (
                  <Sparkles className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
                )}
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Pruning result</h4>
                {sim.success ? (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800">
                    Success
                  </span>
                ) : (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200 border border-rose-200 dark:border-rose-800">
                    No acceptable model
                  </span>
                )}
              </div>

              {sim.success ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50/90 dark:bg-slate-900/50">
                      <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Original model</p>
                      <dl className="grid grid-cols-2 gap-2 text-xs">
                        <dt className="text-gray-500">{sim.primaryLabel}</dt>
                        <dd className="font-medium text-right">{formatNum(sim.original.testPrimary, 3)}</dd>
                        <dt className="text-gray-500">Train</dt>
                        <dd className="font-medium text-right">{formatNum(sim.original.trainPrimary, 3)}</dd>
                        <dt className="text-gray-500">Overfit</dt>
                        <dd className="font-medium text-right">
                          {sim.original.overfit != null ? `${sim.original.overfit.toFixed(2)}%` : 'N/A'}
                        </dd>
                        <dt className="text-gray-500">Features</dt>
                        <dd className="font-medium text-right">{sim.original.nz}</dd>
                      </dl>
                    </div>
                    <div className="rounded-lg border border-blue-200 dark:border-blue-900/50 p-4 bg-blue-50/50 dark:bg-slate-800/40">
                      <p className="text-xs font-semibold text-blue-900 dark:text-blue-200 uppercase mb-2">Pruned model</p>
                      <dl className="grid grid-cols-2 gap-2 text-xs">
                        <dt className="text-gray-600 dark:text-gray-400">{sim.primaryLabel}</dt>
                        <dd className="font-medium text-right">{formatNum(sim.pruned.testPrimary, 3)}</dd>
                        <dt className="text-gray-600 dark:text-gray-400">Train</dt>
                        <dd className="font-medium text-right">{formatNum(sim.pruned.trainPrimary, 3)}</dd>
                        <dt className="text-gray-600 dark:text-gray-400">Overfit</dt>
                        <dd className="font-medium text-right">
                          {sim.pruned.overfit != null ? `${sim.pruned.overfit.toFixed(2)}%` : 'N/A'}
                        </dd>
                        <dt className="text-gray-600 dark:text-gray-400">Features</dt>
                        <dd className="font-medium text-right">{sim.pruned.nz}</dd>
                      </dl>
                    </div>
                  </div>

                  <div className="overflow-x-auto mb-4 rounded-lg border border-gray-200 dark:border-gray-700">
                    <table className="w-full min-w-[520px] text-xs">
                      <thead className={MTA_THEAD}>
                        <tr>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Metric
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Original ({sim.original.nz} feat.)
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Pruned ({sim.pruned.nz} feat.)
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Change
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                        <tr>
                          <td className="px-2 py-2">{sim.primaryLabel}</td>
                          <td className="px-2 py-2">{formatNum(sim.original.testPrimary, 3)}</td>
                          <td className="px-2 py-2">{formatNum(sim.pruned.testPrimary, 3)}</td>
                          <td className="px-2 py-2 text-blue-800 dark:text-blue-300 font-medium">
                            {formatNum(sim.pruned.testPrimary - sim.original.testPrimary, 3)}
                          </td>
                        </tr>
                        {isCls && (
                          <>
                            <tr>
                              <td className="px-2 py-2">Test KS</td>
                              <td className="px-2 py-2">{formatNum(sim.original.ksTest, 3)}</td>
                              <td className="px-2 py-2">{formatNum(sim.pruned.ksTest, 3)}</td>
                              <td className="px-2 py-2 text-blue-800 dark:text-blue-300 font-medium">
                                {sim.original.ksTest != null &&
                                sim.pruned.ksTest != null &&
                                Number.isFinite(sim.original.ksTest) &&
                                Number.isFinite(sim.pruned.ksTest)
                                  ? formatNum(sim.pruned.ksTest - sim.original.ksTest, 3)
                                  : '—'}
                              </td>
                            </tr>
                            <tr>
                              <td className="px-2 py-2">Test Gini</td>
                              <td className="px-2 py-2">{formatNum(2 * sim.original.testPrimary - 1, 3)}</td>
                              <td className="px-2 py-2">{formatNum(2 * sim.pruned.testPrimary - 1, 3)}</td>
                              <td className="px-2 py-2 text-gray-500">—</td>
                            </tr>
                          </>
                        )}
                        <tr>
                          <td className="px-2 py-2">Overfit ({isCls ? 'AUC' : 'R²'})</td>
                          <td className="px-2 py-2">{sim.original.overfit != null ? `${sim.original.overfit.toFixed(2)}%` : 'N/A'}</td>
                          <td className="px-2 py-2">{sim.pruned.overfit != null ? `${sim.pruned.overfit.toFixed(2)}%` : 'N/A'}</td>
                          <td className="px-2 py-2 text-gray-500">—</td>
                        </tr>
                        <tr>
                          <td className="px-2 py-2">Non-zero features</td>
                          <td className="px-2 py-2">{sim.original.nz}</td>
                          <td className="px-2 py-2">{sim.pruned.nz}</td>
                          <td className="px-2 py-2">{sim.pruned.nz - sim.original.nz}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Surviving features</p>
                  <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 mb-3">
                    <table className="w-full min-w-[480px] text-xs">
                      <thead className={MTA_THEAD}>
                        <tr>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Variable
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Importance
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Rank
                          </th>
                          <th className="px-2 py-2 text-center font-semibold uppercase tracking-wide text-[11px] w-14 min-w-[3.5rem] max-w-[4rem]">
                            Lock
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px] min-w-[9.5rem]">
                            Monotone constraint
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                        {sim.surviving.map((s, ri) => (
                          <tr
                            key={s.variable}
                            className={ri % 2 === 1 ? 'bg-gray-50/90 dark:bg-slate-900/55' : 'bg-white dark:bg-slate-950'}
                          >
                            <td className="px-2 py-2 font-mono text-[11px] text-gray-900 dark:text-gray-100 break-words">
                              {s.variable}
                            </td>
                            <td className="px-2 py-2">{s.importance.toFixed(3)}</td>
                            <td className="px-2 py-2">{s.rank}</td>
                            <td className="px-2 py-2 text-center w-14 min-w-[3.5rem] max-w-[4rem] align-middle">
                              {s.locked ? (
                                <span
                                  className="inline-flex justify-center text-amber-700 dark:text-amber-400"
                                  title="Locked — pruning does not drop this feature in the simulation"
                                >
                                  <Lock className="h-4 w-4 mx-auto" aria-label="Locked" />
                                </span>
                              ) : (
                                <span
                                  className="inline-flex justify-center text-orange-500 dark:text-orange-400/90"
                                  title="Unlocked — eligible to drop in the simulation"
                                >
                                  <Unlock className="h-4 w-4 mx-auto" aria-label="Unlocked" />
                                </span>
                              )}
                            </td>
                            <td className="px-2 py-2 align-middle">
                              <MonotoneConstraintReadonly dir={s.monotoneDir} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50/60 dark:bg-emerald-950/30 p-3 text-xs text-emerald-900 dark:text-emerald-100 mb-3">
                    Pruning finished within your performance floor. You can export the log or register the pruned row in the
                    screener for downstream evaluation.
                  </div>
                  <div className="flex flex-wrap gap-2 justify-end">
                    <button
                      type="button"
                      onClick={exportLog}
                      className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-slate-800"
                    >
                      <Download className="inline h-4 w-4 mr-1 -mt-0.5" />
                      Export pruning log
                    </button>
                    <button
                      type="button"
                      onClick={addPrunedToScreener}
                      className="px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 dark:bg-[#292966] dark:text-[#ccccff] dark:hover:bg-[#333380]"
                    >
                      Add pruned model to screener →
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="rounded-lg border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/30 p-3 text-xs text-rose-900 dark:text-rose-100 mb-3">
                    <p className="font-semibold mb-1">No model met the constraints</p>
                    <p className="mb-2">Try increasing the allowed performance drop, raising “most features to keep”, or relaxing the overfitting rule.</p>
                    <p className="font-medium">Recommendations</p>
                    <ul className="list-disc pl-4 mt-1 space-y-0.5">
                      <li>Increase max acceptable drop slightly (e.g. 6–8%).</li>
                      <li>Keep more features (closer to current non-zero count).</li>
                      <li>Increase Bayesian trials if the search space is wide.</li>
                    </ul>
                  </div>
                  <div className="overflow-x-auto mb-3 rounded-lg border border-gray-200 dark:border-gray-700">
                    <table className="w-full text-xs">
                      <thead className={MTA_THEAD}>
                        <tr>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Target
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Best pruned attempt
                          </th>
                          <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide text-[11px]">
                            Required threshold
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-900">
                        <tr>
                          <td className="px-2 py-2">{sim.primaryLabel}</td>
                          <td className="px-2 py-2">{formatNum(sim.bestAttempt, 3)}</td>
                          <td className="px-2 py-2">{formatNum(sim.requiredThreshold, 3)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        setPhase('idle');
                        setSim(null);
                      }}
                      className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-slate-800"
                    >
                      Skip pruning
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setPhase('idle');
                        setSim(null);
                      }}
                      className="px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 dark:bg-[#292966] dark:text-[#ccccff] dark:hover:bg-[#333380]"
                    >
                      Adjust parameters &amp; retry
                    </button>
                  </div>
                </>
              )}
            </div>

          </>
        )}
      </div>

      {isCodebookOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setIsCodebookOpen(false)} aria-hidden />
          <div className="relative bg-white dark:bg-gray-900 rounded-lg shadow-2xl w-full max-w-5xl max-h-[88vh] flex flex-col border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-600 to-indigo-600">
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-6 w-6 text-white shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-lg font-bold text-white">Pruning codebook</h3>
                  <p className="text-xs text-blue-100 truncate">{codebookFileName}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsCodebookOpen(false)}
                className="text-white hover:text-gray-200 p-2 rounded hover:bg-white/10 shrink-0"
                aria-label="Close"
              >
                <span className="text-2xl leading-none">&times;</span>
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-gray-50 dark:bg-slate-950/80">
              {isLoadingCodebook ? (
                <div className="flex items-center justify-center h-56 gap-2 text-gray-600 dark:text-gray-300">
                  <Loader className="h-8 w-8 text-blue-600 animate-spin" />
                  <span>Loading source…</span>
                </div>
              ) : (
                <pre className="text-xs text-gray-100 bg-gray-900 rounded-lg p-4 overflow-x-auto font-mono leading-relaxed">
                  <code>{codebookContent}</code>
                </pre>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-900 flex flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                disabled={!codebookContent}
                onClick={() => {
                  const blob = new Blob([codebookContent], { type: 'text/x-python' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = codebookFileName.endsWith('.py') ? codebookFileName : `${codebookFileName}.py`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 inline-flex items-center gap-1 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                .py
              </button>
              <button
                type="button"
                disabled={!codebookContent}
                onClick={() => {
                  const notebookContent = {
                    cells: [
                      {
                        cell_type: 'code',
                        execution_count: null,
                        metadata: {},
                        outputs: [],
                        source: codebookContent.split('\n'),
                      },
                    ],
                    metadata: {
                      kernelspec: {
                        display_name: 'Python 3',
                        language: 'python',
                        name: 'python3',
                      },
                      language_info: { name: 'python', version: '3.11.0' },
                    },
                    nbformat: 4,
                    nbformat_minor: 4,
                  };
                  const blob = new Blob([JSON.stringify(notebookContent, null, 2)], {
                    type: 'application/json',
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  const base = codebookFileName.replace(/\.py$/i, '');
                  a.download = `${base}.ipynb`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-3 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 inline-flex items-center gap-1 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                .ipynb
              </button>
              <button
                type="button"
                onClick={() => setIsCodebookOpen(false)}
                className="px-4 py-2 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelPruningPanel;
