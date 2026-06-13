import { fastApiService } from './fastApiService';

export interface CorrelationRatioSection {
  analysis_kind?: string;
  title?: string;
  columns: string[];
  rows: Record<string, unknown>[];
  /** Heatmap: numeric variables on rows, categorical on columns (η same as matrix coolwarm in UI). */
  row_labels?: string[];
  column_labels?: string[];
  matrix?: (number | null)[][];
}

export interface CorrelationRatioAnalysisResponse {
  success: boolean;
  dataset_id: string;
  target_variable: string;
  sections: CorrelationRatioSection[];
  message?: string;
  analysis_timestamp?: string;
}

export interface CorrelationRatioAnalyzeParams {
  dataset_id: string;
  target_variable: string;
  categorical_variables?: string[];
  numerical_variables?: string[];
}

function normalizeColumnType(column: Record<string, unknown>): 'Numerical' | 'Categorical' | 'Date' {
  const logicalType = String(column.logical_type ?? column.logicalType ?? '').trim();
  if (logicalType === 'Numerical' || logicalType === 'Categorical' || logicalType === 'Date') {
    return logicalType;
  }
  const rawType = String(column.type ?? '').trim();
  if (rawType === 'Numerical' || rawType === 'Categorical' || rawType === 'Date') {
    return rawType;
  }
  return 'Categorical';
}

function dedupePreserveOrder(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const v of values) {
    if (!v || seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

function getObjectiveVariableFiltersFromSession(targetVariable: string): {
  categorical: string[];
  numerical: string[];
} {
  try {
    const analysisRaw = sessionStorage.getItem('dataset_analysis');
    const configRaw = sessionStorage.getItem('dataset_config');
    const analysis = analysisRaw ? JSON.parse(analysisRaw) : null;
    const config = configRaw ? JSON.parse(configRaw) : null;

    const removed = new Set<string>(
      Array.isArray(config?.variables_to_remove)
        ? (config.variables_to_remove as string[])
        : []
    );

    const columns: Array<Record<string, unknown>> = Array.isArray(analysis?.columns)
      ? (analysis.columns as Array<Record<string, unknown>>)
      : [];

    const categorical: string[] = [];
    const numerical: string[] = [];

    for (const col of columns) {
      const name = String(col?.name ?? '').trim();
      if (!name || name === targetVariable || removed.has(name)) continue;

      const kind = normalizeColumnType(col);
      if (kind === 'Categorical') categorical.push(name);
      if (kind === 'Numerical') numerical.push(name);
    }

    return {
      categorical: dedupePreserveOrder(categorical),
      numerical: dedupePreserveOrder(numerical),
    };
  } catch {
    return { categorical: [], numerical: [] };
  }
}

class CorrelationRatioService {
  private basePath = '/insights/correlation-ratio-analysis';

  async analyze(params: CorrelationRatioAnalyzeParams): Promise<CorrelationRatioAnalysisResponse> {
    const formData = new FormData();
    formData.append('dataset_id', params.dataset_id);
    formData.append('target_variable', params.target_variable);

    const inferred = getObjectiveVariableFiltersFromSession(params.target_variable);
    const categoricalVariables = dedupePreserveOrder(
      (params.categorical_variables && params.categorical_variables.length > 0)
        ? params.categorical_variables
        : inferred.categorical
    );
    const numericalVariables = dedupePreserveOrder(
      (params.numerical_variables && params.numerical_variables.length > 0)
        ? params.numerical_variables
        : inferred.numerical
    );

    if (categoricalVariables.length > 0) {
      formData.append('categorical_variables', JSON.stringify(categoricalVariables));
    }
    if (numericalVariables.length > 0) {
      formData.append('numerical_variables', JSON.stringify(numericalVariables));
    }

    const response = await fastApiService.postInsightFormResolve202(this.basePath, formData);
    const d = response as Record<string, unknown>;
    if (d.success === 1) d.success = true;
    return d as CorrelationRatioAnalysisResponse;
  }
}

export const correlationRatioService = new CorrelationRatioService();
