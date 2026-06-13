/**
 * MEEA Model Evaluation Dashboard - Performance View
 * Focused on comparative model performance metrics (AUC, ROC, CM, Radar, recommendation).
 */

import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  BarChart3,
  RefreshCw,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import modelEvaluationService from '../services/modelEvaluationService';
import { ModelEvaluationData, EvaluationModel } from '../types/modelEvaluation';
import { formatTrainTestPair } from '../utils/displayMissingValue';

// Import comparison components
import ROCCurveComparison from '../components/ModelEvaluation/ROCCurveComparison';
import PerformanceRadarChart from '../components/ModelEvaluation/PerformanceRadarChart';
import ConfusionMatrixComparison from '../components/ModelEvaluation/ConfusionMatrixComparison';
import PerformanceMetricsComparison from '../components/ModelEvaluation/PerformanceMetricsComparison';
import ModelRecommendation from '../components/ModelEvaluation/ModelRecommendation';
import MonotonicityTab from '../components/MonotonicityTab';
import GranularAccuracyTab from '../components/ModelEvaluation/GranularAccuracyTab';

type ModelEvaluationMEEAProps = {
  initialModelIds?: string[];
  datasetId?: string;
  embedMode?: boolean;
  onClose?: () => void;
  defaultMode?: 'standard' | 'segmentation';
};

const ModelEvaluationMEEA: React.FC<ModelEvaluationMEEAProps> = ({
  initialModelIds,
  datasetId,
  embedMode = false,
  defaultMode = 'standard',
}) => {
  const [searchParams] = useSearchParams();
  const modelIdsFromParams = searchParams.get('model_ids')?.split(',') || [];

  // ── Session-storage cache keys & initialiser helpers ──────────────────────
  // These must be declared BEFORE the useState calls that use them as initialisers.
  const _evalCacheKey = datasetId ? `meea_eval_data_${datasetId}` : null;
  const _modelsCacheKey = datasetId ? `meea_available_models_${datasetId}` : null;
  const _selectedIdsCacheKey = datasetId ? `meea_selected_ids_${datasetId}` : null;

  const getInitialEvalData = (): Record<string, ModelEvaluationData> => {
    if (!_evalCacheKey) return {};
    try {
      const cached = sessionStorage.getItem(_evalCacheKey);
      return cached ? JSON.parse(cached) : {};
    } catch { return {}; }
  };
  const getInitialAvailableModels = (): EvaluationModel[] => {
    if (!_modelsCacheKey) return [];
    try {
      const cached = sessionStorage.getItem(_modelsCacheKey);
      return cached ? JSON.parse(cached) : [];
    } catch { return []; }
  };
  const getInitialSelectedIds = (): string[] => {
    // URL params / prop take priority over cache
    if (initialModelIds && initialModelIds.length > 0) return initialModelIds;
    const fromParams = searchParams.get('model_ids')?.split(',') || [];
    if (fromParams.length > 0) return fromParams;
    if (!_selectedIdsCacheKey) return [];
    try {
      const cached = sessionStorage.getItem(_selectedIdsCacheKey);
      return cached ? JSON.parse(cached) : [];
    } catch { return []; }
  };
  // ──────────────────────────────────────────────────────────────────────────

  const [loading, setLoading] = useState(false);
  // Track which individual models are still being fetched so we can show partial results
  const [loadingModelIds, setLoadingModelIds] = useState<Set<string>>(new Set());
  // Per-phase loading state - which phases are still computing across all models
  const [loadingPhase, setLoadingPhase] = useState<1 | 2 | 3 | null>(null);
  // Track which models have each phase ready (for per-tab loading indicators)
  const [phaseReadyModels, setPhaseReadyModels] = useState<Record<1 | 2 | 3, Set<string>>>({
    1: new Set(), 2: new Set(), 3: new Set(),
  });
  const [error, setError] = useState<string | null>(null);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(getInitialSelectedIds);
  const [evaluationData, setEvaluationData] = useState<Record<string, ModelEvaluationData>>(getInitialEvalData);
  const [availableModels, setAvailableModels] = useState<EvaluationModel[]>(getInitialAvailableModels);
  const [refreshing, setRefreshing] = useState(false);
  const [evaluationMode, setEvaluationMode] = useState<'standard' | 'segmentation'>(defaultMode);
  const [activeTab, setActiveTab] = useState<'performance' | 'monotonicity' | 'granular'>('performance');
  const [segmentationData, setSegmentationData] = useState<Record<string, ModelEvaluationData>>({});
  const [segments, setSegments] = useState<Array<{ segment_id: string; count: number }>>([]);
  const [selectedSegment, setSelectedSegment] = useState<string>('');
  const [segmentationModelIds, setSegmentationModelIds] = useState<string[]>([]);
  const [autoSwitchedToSegmentation, setAutoSwitchedToSegmentation] = useState(defaultMode === 'segmentation');
  const [meeaPending, setMeeaPending] = useState(false);
  const meeaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Model colors matching screenshot
  const modelColors = [
    '#3B82F6', // Blue - Logistic Regression
    '#10B981', // Green - Random Forest
    '#F59E0B', // Yellow - XGBoost
    '#8B5CF6', // Purple - Neural Network
    '#EF4444', // Red - Support Vector Machine
  ];

  // Safe sessionStorage helper - strips large data arrays progressively to avoid
  // QuotaExceededError which would crash the whole component tree.
  // ROC/PR curve arrays can be thousands of points each - we strip them first
  // since they are always re-fetched from the phase1 endpoint on demand.
  const safeSessionSet = (key: string, value: unknown) => {
    const _stripEntry = (entry: any, level: 'roc' | 'all') => {
      if (!entry || typeof entry !== 'object') return;
      // Level 1: strip ROC/PR curve arrays (largest data, re-fetched from phase1 endpoint)
      if (level === 'roc' || level === 'all') {
        delete entry.roc_curve;
        delete entry.roc_curve_train;
        delete entry.pr_curve;
        delete entry.pr_curve_train;
      }
      // Level 2: also strip explainability blobs
      if (level === 'all') {
        if (Array.isArray(entry.explainability_data)) entry.explainability_data = [];
        delete entry.shap_analysis;
        delete entry.waterfall_data;
        delete entry.partial_dependence;
      }
    };

    // Attempt 1: store as-is
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
      return;
    } catch { /* quota exceeded - try slimming */ }

    // Attempt 2: strip ROC/PR arrays only
    try {
      const slim = JSON.parse(JSON.stringify(value));
      if (typeof slim === 'object' && slim !== null) {
        Object.values(slim).forEach((entry: any) => _stripEntry(entry, 'roc'));
      }
      sessionStorage.setItem(key, JSON.stringify(slim));
      return;
    } catch { /* still too large */ }

    // Attempt 3: strip everything large
    try {
      const slim = JSON.parse(JSON.stringify(value));
      if (typeof slim === 'object' && slim !== null) {
        Object.values(slim).forEach((entry: any) => _stripEntry(entry, 'all'));
      }
      sessionStorage.setItem(key, JSON.stringify(slim));
    } catch {
      // Give up silently - results will be re-fetched on next visit
    }
  };

  // Persist evaluation data to sessionStorage whenever it changes (strip explainability to save space)
  useEffect(() => {
    if (_evalCacheKey && Object.keys(evaluationData).length > 0) {
      safeSessionSet(_evalCacheKey, evaluationData);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evaluationData]);

  // Persist available models to sessionStorage whenever the list changes
  useEffect(() => {
    if (_modelsCacheKey && availableModels.length > 0) {
      safeSessionSet(_modelsCacheKey, availableModels);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableModels]);

  // Persist selected model IDs to sessionStorage so they survive page navigation
  useEffect(() => {
    if (_selectedIdsCacheKey && selectedModelIds.length > 0) {
      try { sessionStorage.setItem(_selectedIdsCacheKey, JSON.stringify(selectedModelIds)); } catch { /* ignore */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelIds]);

  // Keep a ref to availableModels so the phased fetch effect can read the latest value
  // without needing it as a dependency (avoids re-running on every model list refresh).
  const availableModelsRef = useRef<EvaluationModel[]>(availableModels);
  useEffect(() => { availableModelsRef.current = availableModels; }, [availableModels]);

  // Track previously-pending model IDs so we can fetch newly-completed ones immediately
  const prevPendingIdsRef = useRef<string[]>([]);

  // Listen for custom event from pruned model addition to force a refresh
  useEffect(() => {
    const handlePrunedModelAdded = () => {
      console.log('ModelEvaluationMEEA: Detected new pruned model added, forcing refresh');
      setFetchModelsSignal(s => s + 1);
    };

    window.addEventListener('midas-pruned-screener-queue-changed', handlePrunedModelAdded);
    return () => {
      window.removeEventListener('midas-pruned-screener-queue-changed', handlePrunedModelAdded);
    };
  }, []);

  // Poll MEEA background status - refresh model list once evaluation completes.
  // While evaluation is in progress, poll every 3 s; back off to 8 s once done.
  useEffect(() => {
    if (!datasetId) return;

    const POLL_FAST = 3000;
    const POLL_SLOW = 8000;
    let currentInterval = POLL_FAST;

    const checkMeea = async () => {
      try {
        const status = await modelEvaluationService.getMeeaStatus(datasetId);
        const currentPendingIds: string[] = status.pending_model_ids || [];

        if (status.meea_pending) {
          setMeeaPending(true);

          // Check if any models just completed (were pending before, not pending now)
          const justCompleted = prevPendingIdsRef.current.filter(
            id => !currentPendingIds.includes(id)
          );
          if (justCompleted.length > 0) {
            console.log(`MEEA: ${justCompleted.length} model(s) just completed evaluation:`, justCompleted);
            // Trigger a model list refresh without wiping the existing list
            setFetchModelsSignal(s => s + 1);
          }
          prevPendingIdsRef.current = currentPendingIds;
          currentInterval = POLL_FAST;
        } else if (meeaPending) {
          // Was pending, now all done - clear flag and do a final refresh
          setMeeaPending(false);
          prevPendingIdsRef.current = [];
          // Trigger a refresh without clearing existing data
          setFetchModelsSignal(s => s + 1);
          currentInterval = POLL_SLOW;
        } else {
          setMeeaPending(false);
          currentInterval = POLL_SLOW;
        }
      } catch {
        // Silently ignore polling errors
      }
    };

    checkMeea();
    // Use a ref-based interval so we can dynamically adjust the rate
    const scheduleNext = () => {
      meeaPollRef.current = setTimeout(async () => {
        await checkMeea();
        scheduleNext();
      }, currentInterval);
    };
    scheduleNext();
    return () => {
      if (meeaPollRef.current) clearTimeout(meeaPollRef.current as unknown as ReturnType<typeof setTimeout>);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  // Fetch available models - runs only when the dataset changes or a forced refresh is needed.
  // We intentionally do NOT include selectedModelIds.length or availableModels.length in the
  // dependency array to prevent re-fetching on every selection change or page navigation.
  // The MEEA polling uses a separate ref-based trigger (fetchModelsSignal) when new models complete.
  const [fetchModelsSignal, setFetchModelsSignal] = useState(0);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        if (!datasetId) {
          setAvailableModels([]);
          setSelectedModelIds([]);
          setEvaluationData({});
          return;
        }

        // Skip if we already have models for this dataset and this is not a forced refresh
        // (fetchModelsSignal === 0 means initial mount; > 0 means forced by MEEA completion)
        const cachedModels = availableModelsRef.current;
        if (cachedModels.length > 0 && fetchModelsSignal === 0) {
          console.log('ModelEvaluationMEEA: Models already cached, skipping fetch');
          // Still auto-select if nothing is selected yet
          if (selectedModelIds.length === 0) {
            const globalModels = cachedModels.filter((m: any) => !m.is_segment_model);
            if (globalModels.length > 0) setSelectedModelIds(globalModels.map(m => m.id));
          }
          return;
        }

        console.log('Fetching models by datasetId for MEEA:', datasetId, '(signal:', fetchModelsSignal, ')');
        const response = await modelEvaluationService.listModelsByDataset(datasetId);

        const allModels = response.models || [];
        const modelsWithMEEA = allModels.filter((m: any) => m.has_meea_data === true);

        const filteredModels = evaluationMode === 'standard'
          ? modelsWithMEEA.filter((m: any) => !m.is_segment_model)
          : modelsWithMEEA;

        const sortedModels = filteredModels.sort((a: any, b: any) => {
          const dateA = new Date(a.created_at || a.training_date || 0).getTime();
          const dateB = new Date(b.created_at || b.training_date || 0).getTime();
          return dateB - dateA;
        });

        setAvailableModels(sortedModels);

        // Auto-select all models if nothing is selected yet
        if (!initialModelIds?.length && selectedModelIds.length === 0 && sortedModels.length > 0) {
          setSelectedModelIds(sortedModels.map((m: any) => m.id));
        } else if (evaluationMode === 'standard' && selectedModelIds.length > 0) {
          const filteredSelectedIds = selectedModelIds.filter((id) => {
            const model = modelsWithMEEA.find((m: any) => m.id === id);
            return model ? !(model as any).is_segment_model : sortedModels.some((m: any) => m.id === id);
          });
          if (filteredSelectedIds.length !== selectedModelIds.length) {
            setSelectedModelIds(filteredSelectedIds.length > 0 ? filteredSelectedIds : sortedModels.map((m: any) => m.id));
          } else if (fetchModelsSignal > 0) {
            // Forced refresh (e.g. new models completed evaluation) - add any newly discovered
            // models to the selection so they are fetched and displayed automatically.
            const newModelIds = sortedModels
              .map((m: any) => m.id)
              .filter((id: string) => !selectedModelIds.includes(id));
            if (newModelIds.length > 0) {
              setSelectedModelIds(prev => [...prev, ...newModelIds]);
            }
          }
        }

        if (sortedModels.length === 0 && evaluationMode === 'standard' && !autoSwitchedToSegmentation) {
          setEvaluationMode('segmentation');
          setAutoSwitchedToSegmentation(true);
        }
      } catch (err) {
        console.error('Error fetching models:', err);
        setError('Failed to fetch available models');
      }
    };

    fetchModels();
  // fetchModelsSignal is the intentional trigger for forced refreshes.
  // evaluationMode and autoSwitchedToSegmentation are kept so mode-switches re-filter.
  // selectedModelIds is intentionally excluded to prevent re-fetch on selection change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, initialModelIds?.length, evaluationMode, autoSwitchedToSegmentation, fetchModelsSignal]);

  // Fetch segmentation segments when switching to segmentation mode
  useEffect(() => {
    let isCancelled = false; // Flag to prevent state updates after unmount or mode change
    const fetchSegments = async () => {
      // Early return with explicit checks - don't even attempt the call if conditions aren't met
      if (!datasetId || evaluationMode !== 'segmentation') {
        if (!isCancelled) {
          setSegments([]);
          setError(null);
        }
        return;
      }
      
      // Only proceed if we're definitely in segmentation mode
      try{
        if (!isCancelled) {
          setError(null);
        }
        const response = await modelEvaluationService.listSegmentationIds(datasetId);
        
        // Only update state if we're still in segmentation mode and not cancelled
        if (!isCancelled && evaluationMode === 'segmentation') {
          setSegments(response.segments || []);
        }
      } catch (err: any) {
        // Only set error if we're still in segmentation mode and not cancelled
        if (!isCancelled && evaluationMode === 'segmentation') {
          console.error('Error fetching segmentation ids:', err);
          setError('Failed to fetch segmentation segments');
        }
      }
    };
    
    fetchSegments();
    
    // Cleanup function
    return () => {
      isCancelled = true;
    };
  }, [evaluationMode, datasetId]);

  // Fetch segmentation models when a segment is selected
  useEffect(() => {
    const fetchSegmentModels = async () => {
      if (evaluationMode !== 'segmentation') return;
      if (!datasetId || !selectedSegment) {
        setSegmentationData({});
        setSegmentationModelIds([]);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const response = await modelEvaluationService.listSegmentationModelsBySegment(datasetId, selectedSegment);
        const models = response.models || [];
        const dataMap: Record<string, ModelEvaluationData> = {};
        models.forEach((m: any) => {
          if (m?.model?.id) {
            dataMap[m.model.id] = m as ModelEvaluationData;
          }
        });
        setSegmentationData(dataMap);
        setSegmentationModelIds(models.map((m: any) => m.model.id));
      } catch (err: any) {
        console.error('Error fetching segmentation evaluation data:', err);
        setError('Failed to fetch segmentation evaluation data');
      } finally {
        setLoading(false);
      }
    };
    fetchSegmentModels();
  }, [evaluationMode, datasetId, selectedSegment]);

  // Fetch evaluation data for selected models using a 3-phase progressive approach.
  //
  // Phase 1 (Performance) runs for ALL models in parallel first - user sees the
  // Performance tab for every model as soon as predictions + metrics are done.
  // Phase 2 (Monotonicity) then runs for all models in parallel.
  // Phase 3 (Granular Accuracy) runs last for all models in parallel.
  //
  // Within each phase the frontend polls individual model phase endpoints until
  // the backend has written the phase JSON, then merges the data into evaluationData.
  // This means the user always sees results for all models simultaneously per tab,
  // rather than one model at a time, which gives a complete comparison table faster.
  useEffect(() => {
    if (selectedModelIds.length === 0) return;
    if (evaluationMode === 'segmentation') return;

    if (evaluationMode === 'standard') {
      // Use ref to get current availableModels without it being a dep
      const currentAvailable = availableModelsRef.current;
      if (currentAvailable.length === 0) return;
      const validModelIds = selectedModelIds.filter(id => currentAvailable.some(m => m.id === id));
      if (validModelIds.length === 0) return;
    }

    // Abort controller so we can cancel polling when deps change
    const abortController = new AbortController();
    const { signal } = abortController;

    const runPhasedFetch = async () => {
      setError(null);

      const currentAvailable = availableModelsRef.current;
      const modelsToFetch = evaluationMode === 'standard'
        ? selectedModelIds.filter(id => currentAvailable.some(m => m.id === id))
        : selectedModelIds;

      if (modelsToFetch.length === 0) { setLoading(false); return; }

      // Fetch models that either have no phase1 data at all, OR have phase1 data
      // but are missing ROC curves (they were stripped from sessionStorage to save quota
      // and need to be re-fetched from the phase1 endpoint).
      const _isMissingRoc = (id: string) => {
        const d = evaluationData[id] as any;
        if (!d) return false; // no data at all - handled by the !evaluationData[id] check
        // Regression models never have ROC curves - don't re-fetch for them.
        const problemType: string = d.problem_type || '';
        if (problemType === 'regression') return false;
        // For classification (or unknown problem type), check if ROC data is absent.
        // We treat it as missing only if it's a classification problem.
        const isClassification =
          problemType === 'classification' ||
          d.performance_metrics?.auc_roc !== undefined ||
          d.performance_metrics?.test_auc_roc !== undefined ||
          d.performance_metrics?.train_auc_roc !== undefined;
        if (!isClassification) return false;
        return !d.roc_curve && !d.roc_curve_train;
      };
      const modelsNeedingPhase1 = modelsToFetch.filter(
        id => !evaluationData[id] || _isMissingRoc(id),
      );
      if (modelsNeedingPhase1.length === 0) { setLoading(false); return; }

      if (Object.keys(evaluationData).length === 0) setLoading(true);
      setLoadingModelIds(new Set(modelsNeedingPhase1));

      // ------------------------------------------------------------------
      // Helper: poll a single model's phase endpoint until ready or aborted.
      // For Phase 1: if the phase file isn't found after a few quick attempts,
      // fall back to the comprehensive endpoint (supports models evaluated
      // before the phased approach was introduced).
      // Returns the phase data or null on failure.
      // ------------------------------------------------------------------
      const pollPhase = async (
        modelId: string,
        phase: 1 | 2 | 3,
        maxAttempts = 60,
        intervalMs = 3000,
      ): Promise<any | null> => {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          if (signal.aborted) return null;
          try {
            const result = await modelEvaluationService.getModelEvaluationPhase(modelId, phase);
            if (result.ready && result.data) return result.data;
          } catch { /* ignore transient errors */ }

          // After 3 quick attempts on Phase 1 with no result, try the comprehensive
          // endpoint as a fallback for legacy models that don't have phase files.
          if (phase === 1 && attempt === 2) {
            try {
              const fallback = await modelEvaluationService.getModelEvaluation(modelId, false);
              if (fallback?.evaluation_data) {
                console.log(`[Phase1] Using comprehensive fallback for legacy model ${modelId}`);
                return fallback.evaluation_data;
              }
            } catch { /* comprehensive also not ready yet - keep polling phase endpoint */ }
          }

          if (attempt < maxAttempts - 1) {
            await new Promise(resolve => setTimeout(resolve, intervalMs));
          }
        }
        return null;
      };

      // ------------------------------------------------------------------
      // PHASE 1 - Performance: fetch all models in parallel, update state
      // as each one arrives so the Performance tab renders immediately.
      // ------------------------------------------------------------------
      setLoadingPhase(1);
      const phase1Promises = modelsNeedingPhase1.map(async (modelId) => {
        const data = await pollPhase(modelId, 1);
        if (signal.aborted) return;
          if (data) {
            const isValid = evaluationMode !== 'standard' || availableModelsRef.current.some(m => m.id === modelId);
            if (isValid) {
            setEvaluationData(prev => ({ ...prev, [modelId]: data as ModelEvaluationData }));
            setPhaseReadyModels(prev => ({ ...prev, 1: new Set([...prev[1], modelId]) }));
            console.log(`[Phase1] Performance ready for ${modelId}`);
          }
        }
        // Remove from loading set as each model completes phase 1
        setLoadingModelIds(prev => {
          const next = new Set(prev);
          next.delete(modelId);
          if (next.size === 0) setLoading(false);
          return next;
        });
      });
      await Promise.allSettled(phase1Promises);
      if (signal.aborted) return;
      setLoadingPhase(null);

      // ------------------------------------------------------------------
      // PHASE 2 - Monotonicity: run after all Phase 1 completes.
      // Merge monotonicity data into existing evaluationData entries.
      // ------------------------------------------------------------------
      setLoadingPhase(2);
      const phase2Promises = modelsNeedingPhase1.map(async (modelId) => {
        const data = await pollPhase(modelId, 2);
        if (signal.aborted) return;
        if (data) {
          setEvaluationData(prev => {
            if (!prev[modelId]) return prev;
            return {
              ...prev,
              [modelId]: {
                ...prev[modelId],
                monotonicity_results: data.monotonicity_results ?? prev[modelId].monotonicity_results,
                monotonicity_analysis: data.monotonicity_analysis ?? prev[modelId].monotonicity_analysis,
              } as ModelEvaluationData,
            };
          });
          setPhaseReadyModels(prev => ({ ...prev, 2: new Set([...prev[2], modelId]) }));
          console.log(`[Phase2] Monotonicity ready for ${modelId}`);
        }
      });
      await Promise.allSettled(phase2Promises);
      if (signal.aborted) return;
      setLoadingPhase(null);

      // ------------------------------------------------------------------
      // PHASE 3 - Granular Accuracy: run after all Phase 2 completes.
      // Merge granular accuracy data into existing evaluationData entries.
      // ------------------------------------------------------------------
      setLoadingPhase(3);
      const phase3Promises = modelsNeedingPhase1.map(async (modelId) => {
        const data = await pollPhase(modelId, 3);
        if (signal.aborted) return;
        if (data) {
          setEvaluationData(prev => {
            if (!prev[modelId]) return prev;
            return {
              ...prev,
              [modelId]: {
                ...prev[modelId],
                granular_accuracy: data.granular_accuracy ?? prev[modelId].granular_accuracy,
                granular_accuracy_train: data.granular_accuracy_train ?? prev[modelId].granular_accuracy_train,
              } as ModelEvaluationData,
            };
          });
          setPhaseReadyModels(prev => ({ ...prev, 3: new Set([...prev[3], modelId]) }));
          console.log(`[Phase3] Granular Accuracy ready for ${modelId}`);
        }
      });
      await Promise.allSettled(phase3Promises);
      if (!signal.aborted) setLoadingPhase(null);
    };

    runPhasedFetch();
    return () => abortController.abort();
    // Only re-run when the set of selected model IDs changes or the mode switches.
    // availableModels is intentionally excluded - it changes on every model list refresh
    // but the guard inside (modelsNeedingPhase1) already skips already-loaded models.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelIds.join(','), evaluationMode]);

  // (Explainability-specific effects and handlers removed from this performance-only view)

  const handleRefresh = async () => {
    if (selectedModelIds.length === 0) return;
    setRefreshing(true);
    try {
      // For this performance-only view, we don't need to include explainability payloads on refresh
      const includeExplainability = false;
      const results = await Promise.all(
        selectedModelIds.map(async (modelId) => {
          try {
            const response = await modelEvaluationService.getModelEvaluation(modelId, includeExplainability);
            return { modelId, data: response.evaluation_data };
          } catch (err: any) {
            return { modelId, error: err.response?.data?.detail || 'Failed to fetch evaluation data' };
          }
        })
      );

      const dataMap: Record<string, ModelEvaluationData> = {};
      results.forEach((result) => {
        if (result.data) {
          dataMap[result.modelId] = result.data;
        }
      });

      setEvaluationData(dataMap);
    } catch (err: any) {
      setError('Failed to refresh evaluation data');
    } finally {
      setRefreshing(false);
    }
  };

  // Helper to format train / test metrics for display
  const formatTrainTest = (
    trainValue: number | string | undefined | null,
    testValue: number | string | undefined | null,
    digits: number = 4
  ): string =>
    formatTrainTestPair(
      trainValue,
      testValue,
      (value) => value.toFixed(digits)
    );

  // Prepare data for comparison components
  const prepareComparisonData = () => {
    const sourceData = evaluationMode === 'segmentation' ? segmentationData : evaluationData;
    const models = Object.entries(sourceData).map(([modelId, data], index) => {
      const model =
        (evaluationMode === 'segmentation'
          ? data.model
          : availableModels.find(m => m.id === modelId) || data.model) || data.model;
      
      // In standard mode, filter out segmented models
      if (evaluationMode === 'standard' && model && (model as any).is_segment_model) {
        return null;
      }
      
      const metrics = data.performance_metrics;
      
      // CRITICAL FIX: Properly detect if we have a train/test split
      // Check if test metrics explicitly exist AND differ from train metrics (not fallback values)
      const hasTestSplit = (
        metrics?.test_accuracy !== undefined && 
        metrics?.test_accuracy !== null && 
        metrics?.test_accuracy !== metrics?.train_accuracy
      ) || (
        metrics?.test_f1_score !== undefined && 
        metrics?.test_f1_score !== null && 
        metrics?.test_f1_score !== metrics?.train_f1_score
      );
      
      // Resolve model name - check multiple locations where it may be stored:
      // 1. availableModels list (most reliable, has algorithm display name)
      // 2. data.model.algorithm_name (set by phase1/comprehensive evaluation)
      // 3. data.model_name (top-level field in phase1 JSON)
      // 4. data.model.name (legacy field)
      const resolvedName =
        (availableModels.find(m => m.id === modelId) as any)?.algorithm ||
        (availableModels.find(m => m.id === modelId) as any)?.name ||
        (data as any).model?.algorithm_name ||
        (data as any).model_name ||
        data.model?.name ||
        'Unknown Model';

      return {
        modelName: resolvedName,
        modelId: modelId,
        // PRIMARY METRICS: Use test if split exists, otherwise use train, otherwise use primary
        accuracy: hasTestSplit 
          ? (metrics?.test_accuracy ?? 0) 
          : (metrics?.train_accuracy ?? metrics?.accuracy ?? 0),
        precision: hasTestSplit 
          ? (metrics?.test_precision ?? 0) 
          : (metrics?.train_precision ?? metrics?.precision ?? 0),
        recall: hasTestSplit 
          ? (metrics?.test_recall ?? 0) 
          : (metrics?.train_recall ?? metrics?.recall ?? 0),
        f1Score: hasTestSplit 
          ? (metrics?.test_f1_score ?? 0) 
          : (metrics?.train_f1_score ?? metrics?.f1_score ?? 0),
        aucRoc: hasTestSplit 
          ? (metrics?.test_auc_roc ?? 0) 
          : (metrics?.train_auc_roc ?? metrics?.auc_roc ?? 0),
        aucPr: hasTestSplit 
          ? (metrics?.test_auc_pr ?? undefined) 
          : (metrics?.train_auc_pr ?? metrics?.auc_pr ?? undefined),
        logLoss: hasTestSplit 
          ? (metrics?.test_log_loss ?? undefined) 
          : (metrics?.train_log_loss ?? metrics?.log_loss ?? undefined),

        // EXPLICIT TRAIN/TEST VALUES: Only set if split exists
        trainAccuracy: metrics?.train_accuracy ?? undefined,
        testAccuracy: hasTestSplit ? metrics?.test_accuracy : undefined,
        trainPrecision: metrics?.train_precision ?? undefined,
        testPrecision: hasTestSplit ? metrics?.test_precision : undefined,
        trainRecall: metrics?.train_recall ?? undefined,
        testRecall: hasTestSplit ? metrics?.test_recall : undefined,
        trainF1Score: metrics?.train_f1_score ?? undefined,
        testF1Score: hasTestSplit ? metrics?.test_f1_score : undefined,
        trainAucRoc: metrics?.train_auc_roc ?? undefined,
        testAucRoc: hasTestSplit ? metrics?.test_auc_roc : undefined,
        trainAucPr: metrics?.train_auc_pr ?? undefined,
        testAucPr: hasTestSplit ? metrics?.test_auc_pr : undefined,
        trainLogLoss: metrics?.train_log_loss ?? undefined,
        testLogLoss: hasTestSplit ? metrics?.test_log_loss : undefined,

        // CONFUSION MATRICES
        trainConfusionMatrix: (metrics as any)?.train_confusion_matrix,
        testConfusionMatrix: hasTestSplit ? (metrics as any)?.test_confusion_matrix : undefined,

        color: modelColors[index % modelColors.length],
        parameters: model?.model_type || data.model?.model_type,
        confusionMatrix: metrics?.confusion_matrix,
        
        // ROC curve data for TEST and TRAIN.
        // Phase1 JSON stores ROC data directly as data.roc_curve / data.roc_curve_train.
        // Legacy comprehensive JSON may store it inside data.explainability_data[].
        // We check both locations so both old and new evaluation results work.
        rocData: (() => {
          // 1. Direct field from phase1 JSON (preferred)
          const direct = (data as any).roc_curve;
          if (direct?.fpr && direct?.tpr && direct.fpr.length > 0) {
            console.log(`Model ${modelId}: Found test ROC curve (direct field) with ${direct.fpr.length} points`);
            return direct;
          }
          // 2. Legacy explainability_data array
          if (data.explainability_data && data.explainability_data.length > 0) {
            const rocEntry = data.explainability_data.find(
              d => d.data_type === 'roc_curve' && (d.data_source === 'test' || !d.data_source || d.data_source === undefined)
            );
            if (rocEntry?.values?.fpr && rocEntry.values.tpr && rocEntry.values.fpr.length > 0) {
              console.log(`Model ${modelId}: Found test ROC curve (explainability_data) with ${rocEntry.values.fpr.length} points`);
              return rocEntry.values;
            }
          }
          console.warn(`Model ${modelId}: No test ROC curve found`);
          return null;
        })(),
        
        rocDataTrain: (() => {
          // 1. Direct field from phase1 JSON (preferred)
          const direct = (data as any).roc_curve_train;
          if (direct?.fpr && direct?.tpr && direct.fpr.length > 0) {
            console.log(`Model ${modelId}: Found train ROC curve (direct field) with ${direct.fpr.length} points`);
            return direct;
          }
          // 2. Legacy explainability_data array
          if (data.explainability_data && data.explainability_data.length > 0) {
            const rocEntry = data.explainability_data.find(
              d => d.data_type === 'roc_curve' && d.data_source === 'train'
            );
            if (rocEntry?.values?.fpr && rocEntry.values.tpr && rocEntry.values.fpr.length > 0) {
              console.log(`Model ${modelId}: Found train ROC curve (explainability_data) with ${rocEntry.values.fpr.length} points`);
              return rocEntry.values;
            }
          }
          return null;
        })(),
      };
    }).filter((m): m is NonNullable<typeof m> => m !== null);

    return models;
  };

  const comparisonModels = prepareComparisonData();
  const modelsCount = comparisonModels.length;
  const containerClasses = embedMode
    ? 'w-full bg-white dark:bg-gray-900 min-h-full model-evaluation'
    : 'w-full bg-white dark:bg-gray-900 model-evaluation';

  // (Return/navigation helper removed from this view; navigation is driven by parent containers)

  // Debug logging
  useEffect(() => {
    console.log('=== MEEA Dashboard Debug ===');
    console.log('Available Models:', availableModels.length);
    console.log('Selected Model IDs:', selectedModelIds);
    console.log('Evaluation Data Keys:', Object.keys(evaluationData));
    console.log('Comparison Models:', comparisonModels.length);
    console.log('Loading:', loading);
  }, [availableModels, selectedModelIds, evaluationData, comparisonModels, loading]);

  // Store comparison models in sessionStorage for documentation generation
  // Strip large ROC arrays to avoid QuotaExceededError
  useEffect(() => {
    if (comparisonModels && comparisonModels.length > 0) {
      console.log('💾 Storing', comparisonModels.length, 'comparison models in sessionStorage for documentation');
      const slim = comparisonModels.map(m => ({ ...m, rocData: null, rocDataTrain: null }));
      safeSessionSet('model_comparison_data', slim);
    }
  }, [comparisonModels]);

  useEffect(() => {
    if (initialModelIds && initialModelIds.length > 0) {
      setSelectedModelIds(initialModelIds);
    }
  }, [initialModelIds?.join(',')]);

  useEffect(() => {
    if (!initialModelIds || initialModelIds.length === 0) {
      if (modelIdsFromParams.length > 0) {
        setSelectedModelIds(modelIdsFromParams);
      }
    }
  }, [modelIdsFromParams.join(','), initialModelIds?.join(',')]);

  // When switching back to standard mode, reset selection to available standard models
  // Filter out segmented models when in standard mode
  // Use a ref to track if we've already filtered to prevent infinite loops
  const lastFilteredModeRef = useRef<'standard' | 'segmentation' | null>(null);
  
  useEffect(() => {
    const currentAvailable = availableModelsRef.current;
    if (evaluationMode === 'standard' && currentAvailable.length > 0) {
      const globalModels = currentAvailable.filter((m: any) => !m.is_segment_model);
      const globalModelIds = globalModels.map(m => m.id);

      setSelectedModelIds(prev => {
        const filteredSelectedIds = prev.filter(id => {
          const model = currentAvailable.find(m => m.id === id);
          return model && !(model as any).is_segment_model;
        });
        const needsUpdate = filteredSelectedIds.length !== prev.length ||
                            prev.length === 0 ||
                            lastFilteredModeRef.current !== 'standard';
        if (!needsUpdate) return prev; // no change - avoid re-render
        return filteredSelectedIds.length > 0 ? filteredSelectedIds : globalModelIds;
      });

      // Remove segmented models from evaluationData
      setEvaluationData(prev => {
        const filtered: Record<string, ModelEvaluationData> = {};
        Object.entries(prev).forEach(([modelId, data]) => {
          if (currentAvailable.find(m => m.id === modelId)) filtered[modelId] = data;
        });
        return filtered;
      });

      lastFilteredModeRef.current = 'standard';
    } else if (evaluationMode === 'segmentation') {
      lastFilteredModeRef.current = 'segmentation';
    }
  // Only re-run when evaluationMode changes - availableModels is read via ref
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evaluationMode]);

  return (
    <div className={containerClasses}>
      {/* Header Section - Matching Screenshot */}
      <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center justify-between w-full">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Model Evaluation
              </h1>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600 dark:text-gray-300">Mode:</span>
                <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                  <button
                    className={`px-3 py-1 text-sm ${
                      evaluationMode === 'standard'
                        ? 'bg-blue-50 text-blue-600 font-semibold dark:bg-gray-800 dark:text-white'
                        : 'text-gray-600 dark:text-gray-300'
                    }`}
                    onClick={() => setEvaluationMode('standard')}
                  >
                    Normal
                  </button>
                  <button
                    className={`px-3 py-1 text-sm ${
                      evaluationMode === 'segmentation'
                        ? 'bg-purple-50 text-purple-700 font-semibold dark:bg-gray-800 dark:text-white'
                        : 'text-gray-600 dark:text-gray-300'
                    }`}
                    onClick={() => setEvaluationMode('segmentation')}
                  >
                    Segmentation
                  </button>
                </div>
              </div>
              {evaluationMode === 'segmentation' && (
                <div className="flex items-center gap-2 ml-4">
                  <span className="text-sm text-gray-600 dark:text-gray-300">Segment:</span>
                  <select
                    value={selectedSegment}
                    onChange={(e) => setSelectedSegment(e.target.value)}
                    className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">-- Select segment --</option>
                    {segments.map((s) => (
                      <option key={s.segment_id} value={s.segment_id}>
                        Segment {s.segment_id} ({s.count})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Status Indicators (no close button, no long subtitle) */}
              <div className="flex items-center gap-3">
                <span className="px-3 py-1 bg-green-100 text-green-700 dark:bg-gray-800 dark:text-gray-100 rounded-full text-sm font-semibold">
                  {modelsCount} Models Evaluated
                </span>
                <button
                  onClick={handleRefresh}
                  disabled={refreshing || selectedModelIds.length === 0}
                  className="p-2 bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Refresh data"
                >
                  <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* MEEA background computation banner */}
      {meeaPending && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border-b border-blue-200 dark:border-blue-700 px-4 py-2 flex items-center gap-3">
          <RefreshCw className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" />
          <span className="text-sm text-blue-700 dark:text-blue-300">
            Model evaluation is being computed in the background. Results will appear automatically once ready.
          </span>
        </div>
      )}

      {/* Top-level Tabs: Performance / Monotonicity / Granular Accuracy */}
      <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-2 pt-3 pb-2 overflow-x-auto">
            {([
              { id: 'performance', label: 'Performance', phase: 1 as const },
              { id: 'monotonicity', label: 'Monotonicity', phase: 2 as const },
              { id: 'granular', label: 'Granular Accuracy', phase: 3 as const },
            ] as const).map((tab) => {
              const isPhaseLoading = loadingPhase === tab.phase;
              const phaseHasData = phaseReadyModels[tab.phase].size > 0;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2 rounded-t-lg text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-700 bg-blue-50 dark:bg-gray-800 dark:text-white'
                      : 'border-transparent text-gray-600 hover:text-gray-800 hover:bg-gray-50 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-800'
                  }`}
                >
                  {tab.label}
                  {isPhaseLoading && (
                    <span className="inline-block w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" title="Computing…" />
                  )}
                  {!isPhaseLoading && phaseHasData && (
                    <span className="inline-block w-2 h-2 rounded-full bg-green-500" title="Ready" />
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Full-page spinner only when no data at all yet */}
      {loading && Object.keys(evaluationData).length === 0 && (
        <div className="min-h-[240px] flex items-center justify-center">
          <div className="text-center">
            <div className="relative w-16 h-16 mx-auto mb-4">
              <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-200 rounded-full animate-ping opacity-75"></div>
              <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full animate-spin border-t-transparent"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-blue-600" />
              </div>
            </div>
            <p className="text-gray-700 dark:text-gray-200 font-semibold text-sm">Loading evaluation data...</p>
          </div>
        </div>
      )}
      {/* Inline banner when some models loaded but others still fetching */}
      {loadingModelIds.size > 0 && Object.keys(evaluationData).length > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-700 px-4 py-2 flex items-center gap-3">
          <RefreshCw className="w-4 h-4 text-yellow-600 dark:text-yellow-400 animate-spin flex-shrink-0" />
          <span className="text-sm text-yellow-700 dark:text-yellow-300">
            Loading {loadingModelIds.size} more model(s)… Showing available results below.
          </span>
        </div>
      )}
      {/* Phase-specific progress banner */}
      {loadingPhase !== null && Object.keys(evaluationData).length > 0 && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-700 px-4 py-2 flex items-center gap-3">
          <RefreshCw className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" />
          <span className="text-sm text-blue-700 dark:text-blue-300">
            {loadingPhase === 1 && 'Computing Performance metrics for all models…'}
            {loadingPhase === 2 && 'Performance ready. Computing Monotonicity analysis…'}
            {loadingPhase === 3 && 'Monotonicity ready. Computing Granular Accuracy (this may take a moment)…'}
          </span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/30 dark:border-red-800 dark:text-red-200 px-6 py-4 rounded-lg flex items-center gap-4">
            <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <div className="flex-1">
              <strong className="font-bold">Error Loading Evaluation Data</strong>
              <p className="text-sm mt-1">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800 dark:text-red-300 dark:hover:text-red-200"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* No Models Selected */}
      {!loading && loadingModelIds.size === 0 && evaluationMode === 'standard' && comparisonModels.length === 0 && (
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center bg-white dark:bg-gray-900 rounded-xl shadow-lg p-12 border border-gray-200 dark:border-gray-800">
            <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              {availableModels.length === 0 ? 'No Models Available' : 'No Models Selected'}
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-8">
              {availableModels.length === 0 
                ? 'No models found. Please train some models first using auto-training in Step 7.'
                : 'Models will be automatically loaded and displayed here. If no models appear, they may not have MEEA evaluation data yet.'}
            </p>
            {availableModels.length > 0 && (
              <div className="mt-4 p-4 bg-blue-50 dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-gray-700">
                <p className="text-sm text-blue-800 dark:text-gray-200">
                  Found {availableModels.length} model(s) available. They will be loaded automatically.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {!loading && evaluationMode === 'segmentation' && (
        <>
          {segments.length === 0 && (
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
              <div className="text-center bg-white dark:bg-gray-900 rounded-xl shadow-lg p-12 border border-gray-200 dark:border-gray-800">
                <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Segments Found</h2>
                <p className="text-gray-600 dark:text-gray-300">Run segmentation first to create segment_ids.</p>
              </div>
            </div>
          )}
          {segments.length > 0 && !selectedSegment && (
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
              <div className="text-center bg-white dark:bg-gray-900 rounded-xl shadow-lg p-8 border border-gray-200 dark:border-gray-800">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">Select a Segment</h3>
                <p className="text-gray-600 dark:text-gray-300">Choose a segment to load its evaluation results.</p>
              </div>
            </div>
          )}
          {selectedSegment && comparisonModels.length === 0 && (
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
              <div className="text-center bg-white dark:bg-gray-900 rounded-xl shadow-lg p-12 border border-gray-200 dark:border-gray-800">
                <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Models Evaluated for this Segment</h2>
                <p className="text-gray-600 dark:text-gray-300">We will train/evaluate on-demand when data is available. If this persists, ensure the segment has data and the target is binary.</p>
              </div>
            </div>
          )}
        </>
      )}

      {/* PERFORMANCE TAB - show as soon as at least one model is ready */}
      {comparisonModels.length > 0 && activeTab === 'performance' && (
        <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 pb-16">
          {/* Model Performance Overview - AUC Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {comparisonModels.map((model) => (
              <div 
                key={model.modelId}
                className="bg-white dark:bg-gray-900 rounded-lg p-4 border-2 shadow-sm text-center hover:shadow-md transition-shadow"
                style={{ borderColor: model.color }}
              >
                <div className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">{model.modelName}</div>
                <div 
                  className="text-2xl font-bold mb-1"
                  style={{ color: model.color }}
                >
                  {formatTrainTest(model.trainAucRoc, model.testAucRoc, 3)}
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-300">AUC-ROC (train / test)</div>
              </div>
            ))}
            {/* Skeleton cards for models still loading */}
            {Array.from(loadingModelIds).map(mid => (
              <div key={`loading-${mid}`} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border-2 border-gray-200 dark:border-gray-700 shadow-sm text-center animate-pulse">
                <div className="h-3 bg-gray-200 dark:bg-gray-600 rounded mb-3 mx-4"></div>
                <div className="h-7 bg-gray-200 dark:bg-gray-600 rounded mb-2 mx-6"></div>
                <div className="h-2 bg-gray-200 dark:bg-gray-600 rounded mx-8"></div>
              </div>
            ))}
          </div>

          {/* Interpretation Box */}
          <div className="bg-blue-50 border border-blue-200 dark:bg-gray-800 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-700 dark:text-gray-200">
              <strong>Interpretation:</strong> The ROC curve plots the trade-off between true positive rate and false positive rate. 
              A model with perfect discrimination has AUC = 1.0, while random guessing has AUC = 0.5 (diagonal line). 
              Curves closer to the top-left corner indicate better performance.
            </p>
          </div>

          {/* Deployment Recommendation */}
          <ModelRecommendation 
            models={comparisonModels}
            recommendationReason={
              comparisonModels.length > 0
                ? `${comparisonModels[0].modelName} demonstrates the best balance of predictive performance (AUC-ROC train/test: ${formatTrainTest(comparisonModels[0].trainAucRoc, comparisonModels[0].testAucRoc, 2)}) and fairness metrics (all groups pass 80% threshold). ${comparisonModels.length > 1 ? comparisonModels[1].modelName + ' is a close second with slightly better interpretability. ' : ''}Recommended for production deployment with continued fairness monitoring.`
                : undefined
            }
          />

          {/* Performance Metrics Comparison Table */}
          <PerformanceMetricsComparison 
            models={comparisonModels}
            title="Performance Metrics Comparison"
          />

          {/* ROC Curve Comparison - Train */}
          {(() => {
            const trainModels = comparisonModels
              .filter(m => {
                const hasData = (m as any).rocDataTrain && 
                               Array.isArray((m as any).rocDataTrain.fpr) && 
                               Array.isArray((m as any).rocDataTrain.tpr) &&
                               (m as any).rocDataTrain.fpr.length > 0 &&
                               (m as any).rocDataTrain.tpr.length > 0;
                if (!hasData) {
                  console.log(`Model ${m.modelName} (${m.modelId}): Missing train ROC data`, {
                    hasRocDataTrain: !!(m as any).rocDataTrain,
                    fpr: (m as any).rocDataTrain?.fpr,
                    tpr: (m as any).rocDataTrain?.tpr
                  });
                }
                return hasData;
              })
              .map(m => ({
                modelName: m.modelName,
                modelId: `${m.modelId}-train`,
                rocData: (m as any).rocDataTrain as any,
                color: m.color,
              }));
            
            console.log(`Train ROC models: ${trainModels.length} out of ${comparisonModels.length}`);
            
            return trainModels.length > 0 ? (
              <ROCCurveComparison
                models={trainModels}
                title="ROC Curve Comparison (Train)"
              />
            ) : (
              <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-8 border-2 border-gray-100 dark:border-gray-800">
                <div className="text-center text-gray-500 dark:text-gray-200 py-12">
                  <p className="text-lg font-medium">No train ROC curve data available</p>
                  <p className="text-sm text-gray-400 dark:text-gray-300 mt-2">
                    Train ROC curves will appear here once models are re-evaluated with train data
                  </p>
                </div>
              </div>
            );
          })()}

          {/* ROC Curve Comparison - Test (only if test data exists) */}
          {(() => {
            const testModels = comparisonModels
              .filter(m => {
                const hasData = m.rocData && 
                               Array.isArray(m.rocData.fpr) && 
                               Array.isArray(m.rocData.tpr) &&
                               m.rocData.fpr.length > 0 &&
                               m.rocData.tpr.length > 0;
                return hasData;
              })
              .map(m => ({
                modelName: m.modelName,
                modelId: `${m.modelId}-test`,
                rocData: m.rocData as any,
                color: m.color,
              }));
            
            // Only render if there are test models with data
            return testModels.length > 0 ? (
              <ROCCurveComparison
                models={testModels}
                title="ROC Curve Comparison (Test)"
              />
            ) : null;
          })()}

          {/* Performance Radar Chart - Train */}
          <PerformanceRadarChart
            models={comparisonModels.map(m => ({
              modelName: m.modelName,
              modelId: `${m.modelId}-train`,
              accuracy: m.trainAccuracy ?? m.accuracy,
              precision: m.trainPrecision ?? m.precision,
              recall: m.trainRecall ?? m.recall,
              f1Score: m.trainF1Score ?? m.f1Score,
              aucRoc: m.trainAucRoc ?? m.aucRoc,
              color: m.color,
            }))}
            title="Performance Radar Chart (Train)"
          />

          {/* Performance Radar Chart - Test (only if test metrics exist) */}
          {comparisonModels.some(m => m.testAccuracy !== undefined || m.testAucRoc !== undefined) && (
            <PerformanceRadarChart
              models={comparisonModels
                .filter(m => m.testAccuracy !== undefined || m.testAucRoc !== undefined)
                .map(m => ({
                  modelName: m.modelName,
                  modelId: `${m.modelId}-test`,
                  accuracy: m.testAccuracy ?? 0,
                  precision: m.testPrecision ?? 0,
                  recall: m.testRecall ?? 0,
                  f1Score: m.testF1Score ?? 0,
                  aucRoc: m.testAucRoc ?? 0,
                  color: m.color,
                }))}
              title="Performance Radar Chart (Test)"
            />
          )}

          {/* Confusion Matrix Comparison */}
          {comparisonModels.some(m => m.confusionMatrix || m.trainConfusionMatrix) && (
            <ConfusionMatrixComparison
              models={comparisonModels
                .filter(m => m.confusionMatrix || m.trainConfusionMatrix)
                .map(m => ({
                  modelName: m.modelName,
                  modelId: m.modelId,
                  // Test matrix: only use if testConfusionMatrix exists AND test metrics exist
                  // If no test data, pass undefined so test matrix won't be rendered
                  matrix: (m.testConfusionMatrix !== undefined && (m.testAccuracy !== undefined || m.testF1Score !== undefined))
                    ? m.testConfusionMatrix
                    : (m.testAccuracy !== undefined || m.testF1Score !== undefined
                        ? m.confusionMatrix
                        : (m.confusionMatrix || m.trainConfusionMatrix || [])),
                  trainMatrix: m.trainConfusionMatrix,
                  // Test metrics: only use if explicitly available, otherwise undefined
                  accuracy: m.testAccuracy ?? m.accuracy ?? m.trainAccuracy ?? 0,
                  trainAccuracy: m.trainAccuracy,
                  f1Score: m.testF1Score ?? m.f1Score ?? m.trainF1Score ?? 0,
                  trainF1Score: m.trainF1Score,
                  color: m.color,
                }))}
              title="Confusion Matrix Comparison"
            />
          )}
        </div>
      )}

      {/* MONOTONICITY TAB */}
      {activeTab === 'monotonicity' && (
        <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
          {/* Phase 2 loading indicator */}
          {loadingPhase === 2 && modelsCount > 0 && (
            <div className="mb-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg px-4 py-3 flex items-center gap-3">
              <RefreshCw className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" />
              <span className="text-sm text-blue-700 dark:text-blue-300">
                Computing monotonicity analysis for all models… Showing available results below.
              </span>
            </div>
          )}
          {evaluationMode === 'standard' && modelsCount > 0 && (
            <MonotonicityTab
              availableModels={availableModels.filter((m: any) => !(m as any).is_segment_model)}
              selectedModelIds={selectedModelIds}
              evaluationData={evaluationData}
              loading={loading}
            />
          )}
          {evaluationMode === 'standard' && modelsCount === 0 && !loading && loadingPhase !== 2 && (
            <div className="max-w-4xl mx-auto py-12">
              <div className="bg-white dark:bg-gray-900 rounded-xl shadow-md border border-gray-200 dark:border-gray-800 p-8 text-center text-sm text-gray-600 dark:text-gray-300">
                No evaluated models available for monotonicity diagnostics yet. Train and evaluate at least one model
                first.
              </div>
            </div>
          )}
          {evaluationMode === 'standard' && modelsCount === 0 && loadingPhase === 2 && (
            <div className="max-w-4xl mx-auto py-12 flex items-center justify-center gap-3 text-sm text-gray-500 dark:text-gray-400">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Computing monotonicity analysis…
            </div>
          )}
          {evaluationMode === 'segmentation' && modelsCount > 0 && (
            <MonotonicityTab
              availableModels={comparisonModels.map((m) => ({
                id: m.modelId,
                name: m.modelName,
                model_type: 'segmented',
                task_type: 'classification' as const,
                training_date: new Date().toISOString(),
                status: 'evaluated',
                color: '#8B5CF6',
                created_at: new Date().toISOString(),
                dataset_id: selectedSegment,
                is_segment_model: true,
                segment_id: selectedSegment
              }))}
              selectedModelIds={segmentationModelIds}
              evaluationData={segmentationData}
              loading={loading}
            />
          )}
          {evaluationMode === 'segmentation' && modelsCount === 0 && !loading && (
            <div className="max-w-4xl mx-auto py-12">
              <div className="bg-white rounded-xl shadow-md border border-gray-200 p-8 text-center text-sm text-gray-600">
                No segmented models available for monotonicity diagnostics yet. Select a segment and train models first.
              </div>
            </div>
          )}
        </div>
      )}

      {/* GRANULAR ACCURACY TAB */}
      {activeTab === 'granular' && (
        <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
          {/* Phase 3 loading indicator */}
          {loadingPhase === 3 && modelsCount > 0 && (
            <div className="mb-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg px-4 py-3 flex items-center gap-3">
              <RefreshCw className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" />
              <span className="text-sm text-blue-700 dark:text-blue-300">
                Computing granular accuracy for all models… This may take a moment for large datasets.
              </span>
            </div>
          )}
          {modelsCount === 0 && !loading && loadingModelIds.size === 0 && loadingPhase !== 3 && (
            <div className="max-w-4xl mx-auto py-12">
              <div className="bg-white dark:bg-gray-900 rounded-xl shadow-md border border-gray-200 dark:border-gray-800 p-8 text-center text-sm text-gray-600 dark:text-gray-300">
                No evaluated models available for granular accuracy yet. Train and evaluate at least one classification
                model first.
              </div>
            </div>
          )}
          {modelsCount === 0 && (loading || loadingModelIds.size > 0 || loadingPhase !== null) && (
            <div className="max-w-4xl mx-auto py-12 flex items-center justify-center gap-3 text-sm text-gray-500 dark:text-gray-400">
              <RefreshCw className="w-4 h-4 animate-spin" />
              {loadingPhase === 3 ? 'Computing granular accuracy…' : 'Loading model evaluation data…'}
            </div>
          )}
          {modelsCount > 0 && (
            <GranularAccuracyTab
              evaluationData={evaluationMode === 'segmentation' ? segmentationData : evaluationData}
              comparisonModels={comparisonModels.map((m) => ({
                modelName: m.modelName,
                modelId: m.modelId,
                color: m.color,
              }))}
            />
          )}
        </div>
      )}
      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 mt-12 border-t border-gray-200 dark:border-gray-800">
        <div className="text-center">
          <p className="text-gray-700 dark:text-gray-200 font-semibold mb-2">
            Model Evaluation & Explainability Agent - Agentic ML Workflow System
          </p>
          <p className="text-gray-600 dark:text-gray-300 text-sm">
            Last Updated: {new Date().toLocaleDateString()} | Version: v1.0.0
          </p>
        </div>
      </footer>
    </div>
  );
};

export default ModelEvaluationMEEA;