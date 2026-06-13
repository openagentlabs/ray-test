export interface VariableAnalysisStat {
  variable: string;
  correlation: number | null;
  vif: number | null;
  iv: number | null;
  interpretation?: string;
}

export interface BivariateChartData {
  variable_name: string;
  variable_type: 'categorical' | 'numerical';
  visualization_data: {
    chart_title?: string;
    data: {
      categories: string[];
      bar_data: {
        label: string;
        values: number[];
      };
      line_data: {
        label: string;
        values: number[];
      };
    };
  };
}

export interface ModelSelectionSummary {
  narrative: string;
  finalVariables: {
    totalCount: number;
    categories: Array<{ label: string; count: number; description: string }>;
    attachmentNote: string;
    variableAnalysis?: VariableAnalysisStat[]; // Variable analysis data for used features
    rowsToShow?: number; // Rows filter for variable analysis table
    bivariateAnalysisCharts?: {
      charts: BivariateChartData[]; // Bivariate analysis charts for used features
      variableCount: number | 'all'; // Number of variables to show (default: 4)
      selectedVariables?: string[]; // Optional: specific variables to show
    };
  };
  hyperparameters: {
    tunedValues: Record<string, string | number>;
    summaryList: Array<{ name: string; value: string | number }>;
    searchSpace: Array<{ name: string; range: string }>;
    source: string;
  };
  metadata: {
    algorithm: string;
    optimizationMethod: string;
    iterationCount: number;
    totalModelsTested: number;
    bestScore: number;
    scoreMetric: string;
    generatedAt: string;
  };
}

const DEFAULT_NARRATIVE =
  'The model chosen for this project was an Extreme Gradient Boosting (XGBoost) model. Using Random Sampling in Python, we iteratively tuned hyperparameters until the KS lift stabilized while holding out-of-time (OOT) performance. The objective is to maximize KS on the OOT slice while controlling overfit. This placeholder text is replaced automatically once model training completes.';

const DEFAULT_SEARCH_SPACE: Record<string, Array<{ name: string; range: string }>> = {
  xgboost: [
    { name: 'Gamma', range: '5 - 10' },
    { name: 'Learning rate', range: '0.0025 - 0.10' },
    { name: 'Max depth', range: '3 - 4' },
    { name: 'Min child weight', range: '50 - 100' },
    { name: 'N estimators', range: '200 - 500' },
    { name: 'Subsample', range: '0.80 - 1.00' }
  ],
  default: [
    { name: 'Learning rate', range: '0.001 - 0.1' },
    { name: 'Max depth', range: '3 - 10' },
    { name: 'Regularization', range: '0 - 1' }
  ]
};

const buildDefaultSummary = (): ModelSelectionSummary => ({
  narrative: DEFAULT_NARRATIVE,
  finalVariables: {
    totalCount: 0,
    categories: [],
    attachmentNote: 'Variable manifest will be attached once training outputs are available.',
    rowsToShow: 20,
    bivariateAnalysisCharts: undefined
  },
  hyperparameters: {
    tunedValues: {},
    summaryList: [],
    searchSpace: DEFAULT_SEARCH_SPACE.xgboost,
    source: 'Model Training Agent'
  },
  metadata: {
    algorithm: 'XGBoost',
    optimizationMethod: 'Bayesian optimization',
    iterationCount: 0,
    totalModelsTested: 0,
    bestScore: 0,
    scoreMetric: 'KS',
    generatedAt: new Date().toISOString()
  }
});

const normalizeAlgorithmKey = (algo?: string): string => {
  if (!algo) return 'default';
  const normalized = algo.toLowerCase();
  if (normalized.includes('xgb') || normalized.includes('xgboost')) {
    return 'xgboost';
  }
  return normalized;
};

const pickBestModel = (results: any[], trainingResults?: any): any | null => {
  if (!Array.isArray(results) || results.length === 0) {
    return null;
  }

  // PRIORITY 1: Use best_model_id from training results (aligned with model training agent's composite score selection)
  if (trainingResults) {
    const bestModelId = trainingResults?.best_model_selection?.best_model_id || 
                       trainingResults?.training_results?.best_model_selection?.best_model_id;
    
    if (bestModelId) {
      const foundModel = results.find((r: any) => r.model_id === bestModelId || r.modelId === bestModelId);
      if (foundModel) {
        console.log(`[modelSelectionSummary] Using best_model_id from training agent: ${bestModelId}`);
        return foundModel;
      } else {
        console.warn(`[modelSelectionSummary] Best model ID ${bestModelId} not found in results. Falling back to score-based selection.`);
      }
    }
  }

  // PRIORITY 2: Fallback to score-based selection (original logic)
  const scoreForModel = (model: any): number => {
    if (!model) return 0;
    const metrics = model.metrics || {};
    if (typeof model.best_score === 'number') return model.best_score;
    if (typeof metrics.ks === 'number') return metrics.ks;
    if (typeof metrics.auc === 'number') return metrics.auc;
    if (typeof metrics.accuracy === 'number') return metrics.accuracy;
    if (typeof metrics.r2 === 'number') return metrics.r2;
    return 0;
  };

  return results.reduce((best, current) => {
    if (!best) return current;
    return scoreForModel(current) > scoreForModel(best) ? current : best;
  }, null as any);
};

const getBestScoreInfo = (model: any): { metric: string; value: number } => {
  if (!model) {
    return { metric: 'KS', value: 0 };
  }

  if (typeof model.best_score === 'number') {
    return { metric: 'Best score', value: model.best_score };
  }

  const metrics = model.metrics || {};
  if (typeof metrics.ks === 'number') {
    return { metric: 'KS', value: metrics.ks };
  }
  if (typeof metrics.auc === 'number') {
    return { metric: 'AUC', value: metrics.auc };
  }
  if (typeof metrics.f1 === 'number') {
    return { metric: 'F1', value: metrics.f1 };
  }
  if (typeof metrics.accuracy === 'number') {
    return { metric: 'Accuracy', value: metrics.accuracy };
  }
  if (typeof metrics.r2 === 'number') {
    return { metric: 'R²', value: metrics.r2 };
  }

  return { metric: 'Score', value: 0 };
};

const formatNarrative = (
  algorithm: string,
  optimizationMethod: string,
  iterationCount: number,
  totalModelsTested: number,
  scoreInfo: { metric: string; value: number }
): string => {
  const formattedScore = scoreInfo.value ? scoreInfo.value.toFixed(scoreInfo.metric === 'KS' ? 2 : 4) : 'N/A';
  const iterationText = iterationCount > 0 ? `${iterationCount} iterations` : 'multiple iterations';
  const modelRuns = totalModelsTested > 0 ? `${totalModelsTested} model configurations` : 'several configurations';

  return `The model chosen for this project was an ${algorithm} model. Using ${optimizationMethod} in Python, hyper-parameter tuning explored ${modelRuns} and completed ${iterationText}. The ${scoreInfo.metric} observed on the out-of-time evaluation window peaked at ${formattedScore}, which satisfied both lift and overfit criteria.`;
};

export const buildModelSelectionSummary = (trainingResults: any): ModelSelectionSummary => {
  if (!trainingResults) {
    return buildDefaultSummary();
  }

  const results = trainingResults.results || [];
  const usedFeatures: string[] = trainingResults.used_features || trainingResults.usedFeatures || [];
  // Pass trainingResults to pickBestModel so it can use best_model_id if available
  const bestModel = pickBestModel(results, trainingResults);
  const algorithmRaw = bestModel?.algorithm || trainingResults.algorithm || 'XGBoost';
  const algorithm = algorithmRaw.replace(/_/g, ' ').toUpperCase();
  
  // Determine optimization method:
  // - Auto Training: Always Bayesian Optimization
  // - Manual Training: Use actual optimization_method from best model
  let optimizationMethod: string;
  if (trainingResults?.auto_selection_summary?.training_method === 'fully_automatic') {
    // Auto Training: Always Bayesian Optimization
    optimizationMethod = 'Bayesian Optimization';
  } else {
    // Manual Training: Check actual optimization_method from best model
    if (bestModel?.optimization_method) {
      const optMethod = bestModel.optimization_method.toLowerCase();
      if (optMethod === 'bayesian_optimization' || optMethod === 'bayesian_optuna' || optMethod === 'bayesian') {
        optimizationMethod = 'Bayesian Optimization';
      } else if (optMethod === 'random_search' || optMethod === 'random') {
        optimizationMethod = 'Random Sampling';
      } else {
        // Format other methods nicely
        optimizationMethod = optMethod.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
      }
    } else {
      // Fallback: Default to manual experimentation if no optimization_method found
      optimizationMethod = 'manual experimentation';
    }
  }
  const iterationHistory: any[] = bestModel?.iteration_history || bestModel?.iterationHistory || [];
  const iterationCount = Array.isArray(iterationHistory) ? iterationHistory.length : 0;
  const totalModelsTested = trainingResults?.auto_selection_summary?.num_models_trained || results.length || 0;
  const scoreInfo = getBestScoreInfo(bestModel);

  const narrative = formatNarrative(algorithm, optimizationMethod, iterationCount, totalModelsTested, scoreInfo);

  const topFeatures = usedFeatures.slice(0, Math.min(usedFeatures.length, 12));
  const remainingCount = usedFeatures.length - topFeatures.length;
  const categories: Array<{ label: string; count: number; description: string }> = [];

  if (topFeatures.length) {
    categories.push({
      label: 'Top contributors',
      count: topFeatures.length,
      description: topFeatures.join(', ')
    });
  }

  if (remainingCount > 0) {
    categories.push({
      label: 'Additional engineered variables',
      count: remainingCount,
      description: `${remainingCount} more variables retained after stability checks.`
    });
  }

  const hyperparameters = bestModel?.hyperparameters || {};
  const summaryList = Object.entries(hyperparameters).map(([name, value]) => ({
    name,
    value: typeof value === 'number' || typeof value === 'string' ? value : JSON.stringify(value),
  }));

  // PRIORITY 1: Use actual hyperparameter search space from training results if available
  // This comes from the first result that has hyperparameter_search_space
  let searchSpace = DEFAULT_SEARCH_SPACE.default;
  
  if (Array.isArray(results) && results.length > 0) {
    // Find the first result with hyperparameter_search_space (usually the best model)
    const resultWithSearchSpace = results.find((r: any) => r.hyperparameter_search_space && Array.isArray(r.hyperparameter_search_space));
    if (resultWithSearchSpace && resultWithSearchSpace.hyperparameter_search_space.length > 0) {
      searchSpace = resultWithSearchSpace.hyperparameter_search_space;
      console.log(`[modelSelectionSummary] Using actual hyperparameter_search_space from training results for ${algorithmRaw}`);
    } else {
      // PRIORITY 2: Fallback to algorithm-specific default if no actual search space found
      const searchSpaceKey = normalizeAlgorithmKey(algorithmRaw);
      searchSpace = DEFAULT_SEARCH_SPACE[searchSpaceKey] || DEFAULT_SEARCH_SPACE.default;
    }
  } else {
    // PRIORITY 3: Use algorithm-specific default
    const searchSpaceKey = normalizeAlgorithmKey(algorithmRaw);
    searchSpace = DEFAULT_SEARCH_SPACE[searchSpaceKey] || DEFAULT_SEARCH_SPACE.default;
  }

  return {
    narrative,
    finalVariables: {
      totalCount: usedFeatures.length,
      categories,
      attachmentNote: '',
      rowsToShow: 20,
      bivariateAnalysisCharts: undefined
    },
    hyperparameters: {
      tunedValues: hyperparameters,
      summaryList,
      searchSpace,
      source: 'Model Training Agent'
    },
    metadata: {
      algorithm,
      optimizationMethod,
      iterationCount,
      totalModelsTested,
      bestScore: scoreInfo.value,
      scoreMetric: scoreInfo.metric,
      generatedAt: new Date().toISOString()
    }
  };
};

export const getDefaultModelSelectionSummary = buildDefaultSummary;
