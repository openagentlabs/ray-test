/**
 * Step 3 — Auto Data Insights: prefetch Bivariate, Correlation vs target, Correlation matrix,
 * Correlation ratio (η), IV, and VIF via REST (/insights/*).
 */
import { bivariateAnalysisService } from './bivariateAnalysisService';
import { correlationAnalysisService } from './correlationAnalysisService';
import { multicollinearityService } from './multicollinearityService';
import { correlationRatioService } from './correlationRatioService';
import { ivAnalysisService } from './ivAnalysisService';
import { vifAnalysisService } from './vifAnalysisService';

export type AutoInsightApiStepId =
  | 'bivariate_analysis'
  | 'correlation_analysis'
  | 'correlation_matrix'
  | 'correlation_ratio_analysis'
  | 'iv_analysis'
  | 'variance_inflation_factor';

/** Same IDs the Step 3 checklist uses; REST prefetch targets a subset when running Standard insights. */
export const REST_PREFETCHABLE_INSIGHT_STEPS: readonly AutoInsightApiStepId[] = [
  'bivariate_analysis',
  'correlation_analysis',
  'correlation_matrix',
  'correlation_ratio_analysis',
  'iv_analysis',
  'variance_inflation_factor',
] as const;

export function filterToPrefetchableInsightSteps(selected: string[]): AutoInsightApiStepId[] {
  const allowed = new Set<string>(REST_PREFETCHABLE_INSIGHT_STEPS);
  const out: AutoInsightApiStepId[] = [];
  for (const s of selected) {
    if (allowed.has(s)) out.push(s as AutoInsightApiStepId);
  }
  return out;
}

export type AutoInsightStepStatus = 'idle' | 'running' | 'done' | 'absent' | 'error';

export type RunAutoInsightApiPrefetchesOptions = {
  /** If set, only these insight REST calls run (Standard mode with selected features). Omit or empty = all steps (Auto). */
  onlyStepIds?: AutoInsightApiStepId[] | null;
};

async function prefetchCorrelationMatrix(datasetId: string, targetVariable: string): Promise<void> {
  const data = await multicollinearityService.getFullCorrelationMatrixData(
    datasetId,
    targetVariable,
    'pearson'
  );
  const hasMatrix =
    data?.correlation_matrix &&
    typeof data.correlation_matrix === 'object' &&
    Object.keys(data.correlation_matrix).length > 0;
  if (!hasMatrix) {
    throw new Error('Correlation matrix is empty');
  }
}

async function prefetchCorrelationRatio(datasetId: string, targetVariable: string): Promise<void> {
  const data = await correlationRatioService.analyze({
    dataset_id: datasetId,
    target_variable: targetVariable,
  });
  const sections = Array.isArray(data?.sections) ? data.sections : [];
  const hasHeatmap = sections.some(
    (s: { analysis_kind?: string; matrix?: unknown[][]; row_labels?: unknown[] }) =>
      s?.analysis_kind === 'correlation_ratio_categorical_numeric_heatmap' &&
      Array.isArray(s?.matrix) &&
      s.matrix.length > 0 &&
      Array.isArray(s?.row_labels) &&
      s.row_labels.length > 0
  );
  const hasRows = sections.some((s: { rows?: unknown[] }) => Array.isArray(s?.rows) && s.rows.length > 0);
  if (!hasHeatmap && !hasRows) {
    throw new Error('Correlation ratio analysis returned no rows');
  }
}

async function prefetchIvAnalysis(datasetId: string, targetVariable: string): Promise<void> {
  const data = await ivAnalysisService.analyzeAllVariables({
    dataset_id: datasetId,
    target_variable: targetVariable,
  });
  const n = data?.analysis_results ? Object.keys(data.analysis_results).length : 0;
  if (!data?.success || n === 0) {
    throw new Error('IV analysis returned no variables');
  }
}

async function prefetchVifAnalysis(datasetId: string, targetVariable: string): Promise<void> {
  const data = await vifAnalysisService.analyzeAllVariables({
    dataset_id: datasetId,
    target_variable: targetVariable,
  });
  const n = data?.analysis_results ? Object.keys(data.analysis_results).length : 0;
  if (!data?.success || n === 0) {
    throw new Error('VIF analysis returned no variables');
  }
}

/**
 * Runs insight API calls independently. Invokes onStepComplete with 'done' or 'error' per step as each completes.
 * Auto mode: omit `onlyStepIds` to prefetch all. Standard mode: pass `onlyStepIds` matching the user's selected features.
 */
export async function runAutoInsightApiPrefetches(
  datasetId: string,
  targetVariable: string,
  onStepComplete: (
    stepId: AutoInsightApiStepId,
    status: Exclude<AutoInsightStepStatus, 'idle' | 'running'>
  ) => void,
  options?: RunAutoInsightApiPrefetchesOptions
): Promise<void> {
  const allTasks: Array<{ id: AutoInsightApiStepId; run: () => Promise<any> }> = [
    {
      id: 'bivariate_analysis',
      run: () =>
        bivariateAnalysisService.analyzeAllVariables({
          dataset_id: datasetId,
          target_variable: targetVariable,
        }),
    },
    {
      id: 'correlation_analysis',
      run: () =>
        correlationAnalysisService.analyzeCorrelations({
          dataset_id: datasetId,
          target_variable: targetVariable,
          correlation_threshold: 0.05,
          correlation_method: 'pearson',
        }),
    },
    {
      id: 'correlation_matrix',
      run: () => prefetchCorrelationMatrix(datasetId, targetVariable),
    },
    {
      id: 'correlation_ratio_analysis',
      run: () => prefetchCorrelationRatio(datasetId, targetVariable),
    },
    {
      id: 'iv_analysis',
      run: () => prefetchIvAnalysis(datasetId, targetVariable),
    },
    {
      id: 'variance_inflation_factor',
      run: () => prefetchVifAnalysis(datasetId, targetVariable),
    },
  ];

  const want = options?.onlyStepIds?.length
    ? new Set(options.onlyStepIds)
    : null;
  const tasks = want ? allTasks.filter((t) => want.has(t.id)) : allTasks;

  if (tasks.length === 0) {
    return;
  }

  // Run each task independently and update status as each completes
  tasks.forEach(({ id, run }) => {
    run()
      .then(() => {
        onStepComplete(id, 'done');
      })
      .catch((e) => {
        console.error(`[autoInsights] ${id} failed:`, e);
        onStepComplete(id, 'error');
      });
  });
}
