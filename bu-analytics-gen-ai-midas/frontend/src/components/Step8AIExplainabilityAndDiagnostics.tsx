import React, { useEffect, useState, useRef, useMemo } from 'react';
import {
  FileText,
  RefreshCw,
  AlertTriangle,
  Loader2,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';

import { ModelEvaluationData, EvaluationModel } from '../types/modelEvaluation';
import { modelEvaluationService } from '../services/modelEvaluationService';
import ExplainabilityTab from './ExplainabilityTab';

type ExplainabilityTabId = 'shap' | 'pdp';

interface Step8AIExplainabilityAndDiagnosticsProps {
  datasetId?: string | null;
}

type DiagnosticsCacheEntry = {
  activeTab: ExplainabilityTabId;
  availableModels: EvaluationModel[];
  selectedModelIds: string[];
  evaluationData: Record<string, ModelEvaluationData>;
  explainabilityDataSource: 'train' | 'test';
  explainabilityDataLoaded: Set<string>;
  recalculatingExplainability: Record<string, 'train' | 'test'>;
};

const diagnosticsCache: Record<string, DiagnosticsCacheEntry> = {};

const getCacheKey = (datasetId?: string | null): string => (datasetId ? String(datasetId) : '__global__');

const getInitialCacheEntry = (key: string, evaluationData?: Record<string, ModelEvaluationData>): DiagnosticsCacheEntry => {
  if (diagnosticsCache[key]) {
    return diagnosticsCache[key];
  }
  
  // Determine default data source: use 'train' if no test data exists, otherwise 'test'
  let defaultDataSource: 'train' | 'test' = 'test';
  if (evaluationData) {
    // Check if any model has test explainability data
    const hasTestData = Object.values(evaluationData).some(data => {
      return data.explainability_data?.some((d: any) => {
        const ds = d.data_source;
        return ds === 'test' || ds === null || ds === undefined || ds === '';
      });
    });
    // Check if any model has train explainability data
    const hasTrainData = Object.values(evaluationData).some(data => {
      return data.explainability_data?.some((d: any) => d.data_source === 'train');
    });
    
    // If no test data but train data exists, default to 'train'
    if (!hasTestData && hasTrainData) {
      defaultDataSource = 'train';
    }
  }
  
  const entry: DiagnosticsCacheEntry = {
    activeTab: 'shap',
    availableModels: [],
    selectedModelIds: [],
    evaluationData: evaluationData || {},
    explainabilityDataSource: defaultDataSource,
    explainabilityDataLoaded: new Set<string>(),
    recalculatingExplainability: {},
  };
  diagnosticsCache[key] = entry;
  return entry;
};

const Step8AIExplainabilityAndDiagnostics: React.FC<Step8AIExplainabilityAndDiagnosticsProps> = ({ datasetId }) => {
  const SAMPLES_PAGE_SIZE = 50;
  const cacheKey = getCacheKey(datasetId);
  const initialCache = getInitialCacheEntry(cacheKey);

  // Core state is initialized from (and later persisted back to) the module-level cache
  const [activeTab, setActiveTab] = useState<ExplainabilityTabId>(initialCache.activeTab);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<EvaluationModel[]>(initialCache.availableModels);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(initialCache.selectedModelIds);
  const [evaluationData, setEvaluationData] = useState<Record<string, ModelEvaluationData>>(
    initialCache.evaluationData,
  );

  const [explainabilityDataSource, setExplainabilityDataSource] = useState<'train' | 'test'>(
    initialCache.explainabilityDataSource,
  );
  const [recalculatingExplainability, setRecalculatingExplainability] = useState<
    Record<string, 'train' | 'test'>
  >(initialCache.recalculatingExplainability);
  const [loadingExplainability, setLoadingExplainability] = useState(false);
  const [explainabilityDataLoaded, setExplainabilityDataLoaded] = useState<Set<string>>(
    initialCache.explainabilityDataLoaded,
  );
  // Ref to track if we're refreshing explainability (to prevent loading states from hiding content)
  const isRefreshingExplainabilityRef = useRef(false);
  // Raw samples for record-level exploration (actual rows used in train/test)
  // NOTE: currently wired for backend integration and debugging; UI wiring will follow.
  // Samples and meta are currently only logged for development; UI wiring will follow.
  const [samples, setSamples] = useState<
    Array<{
      sample_index: number;
      row_index: number | string;
      id_value?: string | number | null;
      target?: string | number | null;
      features: Record<string, any>;
    }>
  >([]);
  const [samplesMeta, setSamplesMeta] = useState<{ total: number; loading: boolean }>({
    total: 0,
    loading: false,
  });
  const [selectedSampleIndex, setSelectedSampleIndex] = useState<number | null>(null);
  const [samplesPage, setSamplesPage] = useState<number>(0);
  const [samplesSearchQuery, setSamplesSearchQuery] = useState<string>('');
  const [samplesError, setSamplesError] = useState<string | null>(null);
  // Track which model's samples to fetch (set when opening record browser from a specific model)
  const [selectedModelForSamples, setSelectedModelForSamples] = useState<string | null>(null);
  // Track the currently selected waterfall model (for initial samples fetch)
  const [currentWaterfallModel, setCurrentWaterfallModel] = useState<string | null>(null);
  // Track which model the current samples belong to (to prevent showing wrong columns)
  const [samplesModelId, setSamplesModelId] = useState<string | null>(null);
  // Track the target column name for the current samples
  const [samplesTargetColumn, setSamplesTargetColumn] = useState<string | null>(null);

  const recalculatingExplainabilityRef = useRef<Record<string, 'train' | 'test'>>({});
  const explainabilityDataSourceRef = useRef<'train' | 'test'>('test');
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const isExplainabilityActive = activeTab === 'shap' || activeTab === 'pdp';

  useEffect(() => {
    recalculatingExplainabilityRef.current = recalculatingExplainability;
  }, [recalculatingExplainability]);

  useEffect(() => {
    explainabilityDataSourceRef.current = explainabilityDataSource;
  }, [explainabilityDataSource]);

  // When any core state changes, persist it back into the cache for this dataset
  useEffect(() => {
    diagnosticsCache[cacheKey] = {
      activeTab,
      availableModels,
      selectedModelIds,
      evaluationData,
      explainabilityDataSource,
      explainabilityDataLoaded,
      recalculatingExplainability,
    };
  }, [
    cacheKey,
    activeTab,
    availableModels,
    selectedModelIds,
    evaluationData,
    explainabilityDataSource,
    explainabilityDataLoaded,
    recalculatingExplainability,
  ]);

  // Fetch available models for the given dataset and auto-select them.
  // In the wizard, if there is no active dataset, we don't list global models.
  const fetchModels = async () => {
    try {
      setLoading(true);
      setError(null);

      if (!datasetId) {
        // No active dataset: do not load or display global models for Step 8
        console.log('Step8: No active dataset, skipping global model listing for AI Explainability');
        setAvailableModels([]);
        setSelectedModelIds([]);
        setLoading(false); // Clear loading state when no dataset
        return;
      } else {
        const response = await modelEvaluationService.listModelsByDataset(datasetId);

        const allModels = response.models || [];
        const modelsWithMEEA = allModels.filter((m: any) => m.has_meea_data === true);

        const sortedModels = modelsWithMEEA.sort((a, b) => {
          const dateA = new Date(a.created_at || a.training_date || 0).getTime();
          const dateB = new Date(b.created_at || b.training_date || 0).getTime();
          return dateB - dateA;
        });

        setAvailableModels(sortedModels);
        const allModelIds = sortedModels.map((m: EvaluationModel) => m.id);
        // Auto-select all models, preserving existing selections and adding new ones
        setSelectedModelIds((prev) => {
          // Keep previously selected models that still exist, and add any new models
          const existingSelected = prev.filter(id => sortedModels.some(m => m.id === id));
          const newModels = allModelIds.filter(id => !prev.includes(id));
          const newSelectedIds = newModels.length > 0 ? [...existingSelected, ...newModels] : (prev.length > 0 ? prev : allModelIds);
          
          // Note: Loading state will be cleared by fetchEvaluationData useEffect
          // which runs when selectedModelIds changes
          
          return newSelectedIds;
        });
        
        // Check if we already have evaluation data for current models
        // This handles the case where selectedModelIds doesn't change (same models on refresh)
        const currentSelectedIds = selectedModelIds.length > 0 ? selectedModelIds : allModelIds;
        const hasAllEvaluationData = currentSelectedIds.length > 0 && currentSelectedIds.every(id => evaluationData[id]);
        
        if (hasAllEvaluationData) {
          // Already have evaluation data for all models, clear loading
          // Use a small delay to allow fetchEvaluationData to run first if selectedModelIds changed
          setTimeout(() => {
            setLoading(false);
          }, 100);
        } else if (!isExplainabilityActive || sortedModels.length === 0) {
          // Not on explainability tab or no models, clear loading immediately
          setLoading(false);
        }
        // Otherwise, keep loading true - fetchEvaluationData will handle setting it to false when it runs
      }
    } catch (err) {
      console.error('Error fetching models for AI Explainability dashboard:', err);
      setError('Failed to fetch available models for explainability');
      setLoading(false);
    }
  };

  // Initial fetch when datasetId changes
  useEffect(() => {
    fetchModels();
  }, [datasetId]);

  // Re-fetch models when explainability tab becomes active to pick up newly trained models
  useEffect(() => {
    if (isExplainabilityActive && datasetId) {
      // Set loading state immediately when switching to explainability tab
      // This ensures loading indicator shows right away
      setLoading(true);
      fetchModels();
    }
  }, [activeTab, datasetId, isExplainabilityActive]);

  // Ensure evaluation data is fetched when switching to explainability tab
  // even if selectedModelIds hasn't changed (e.g., after page refresh)
  useEffect(() => {
    if (isExplainabilityActive && selectedModelIds.length > 0) {
      // Check if we need to fetch evaluation data
      const needsEvaluationData = selectedModelIds.some(id => !evaluationData[id]);
      if (needsEvaluationData) {
        // Trigger evaluation data fetch by ensuring loading is true
        // The existing useEffect for selectedModelIds will handle the actual fetch
        setLoading(true);
      } else {
        // If we already have all evaluation data, clear loading state
        setLoading(false);
      }
    }
  }, [activeTab, selectedModelIds, evaluationData]);

  // Note: Explainability tab supports both global and segmented models
  
  // Note: Explainability tab supports both global and segmented models, so no filtering needed

  // Auto-switch to 'train' data source if no test data exists (active_scope == 'entire')
  useEffect(() => {
    if (Object.keys(evaluationData).length === 0) return;
    
    // Check if any model has test explainability data
    const hasTestData = Object.values(evaluationData).some(data => {
      return data.explainability_data?.some((d: any) => {
        const ds = d.data_source;
        return ds === 'test' || ds === null || ds === undefined || ds === '';
      });
    });
    // Check if any model has train explainability data
    const hasTrainData = Object.values(evaluationData).some(data => {
      return data.explainability_data?.some((d: any) => d.data_source === 'train');
    });
    
    // If no test data but train data exists, and we're currently on 'test', switch to 'train'
    if (!hasTestData && hasTrainData && explainabilityDataSource === 'test') {
      console.log('No test explainability data found, switching to train data source');
      setExplainabilityDataSource('train');
    }
  }, [evaluationData, explainabilityDataSource]);

  // Reset samples paging when model selection or data source changes
  useEffect(() => {
    setSamplesPage(0);
    // Reset selectedModelForSamples only when model selection changes (not on search)
    setSelectedModelForSamples(null);
    // Reset currentWaterfallModel when model selection changes
    setCurrentWaterfallModel(null);
    // Reset selected sample when data source changes (will auto-select first sample after fetch)
    setSelectedSampleIndex(null);
  }, [selectedModelIds, explainabilityDataSource, datasetId]);
  
  // Reset page (but not selectedModelForSamples or currentWaterfallModel) when search query changes
  useEffect(() => {
    setSamplesPage(0);
  }, [samplesSearchQuery]);

  // Fetch raw samples (actual rows) for the currently selected model & data source.
  // This enables a future record browser where users can pick a specific record
  // to generate a waterfall explanation, without affecting existing charts.
  useEffect(() => {
    if (!isExplainabilityActive) return;
    if (!selectedModelIds.length) return;

    // Use selectedModelForSamples if set (when opening record browser from a specific model),
    // otherwise use currentWaterfallModel (currently selected waterfall model),
    // finally fall back to the first selected model
    // This ensures samples are always fetched for the correct model
    const currentModelId = selectedModelForSamples || currentWaterfallModel || selectedModelIds[0];
    
    // Log for debugging
    console.log(`Step8 samples fetch: selectedModelForSamples=${selectedModelForSamples}, currentWaterfallModel=${currentWaterfallModel}, using modelId=${currentModelId}`);

    const fetchSamples = async () => {
      try {
        setSamplesError(null);
        setSamplesMeta((prev) => ({ ...prev, loading: true }));
        const offset = samplesPage * SAMPLES_PAGE_SIZE;
        const res = await modelEvaluationService.listSamples(
          currentModelId,
          explainabilityDataSource,
          offset,
          SAMPLES_PAGE_SIZE,
          samplesSearchQuery,
        );
        setSamples(res.samples || []);
        setSamplesMeta({ total: res.total || 0, loading: false });
        // Track which model these samples belong to
        setSamplesModelId(currentModelId);
        // Store target column name from API response
        setSamplesTargetColumn(res.target_column || null);
        console.log(
          `Step8 Explainability samples for model ${currentModelId} (${res.data_source}): loaded=${res.samples.length}, total=${res.total}`,
          { samplesPreview: res.samples.slice(0, 3), offset, search: samplesSearchQuery },
        );
      } catch (err: any) {
        console.error('Error fetching samples for explainability record browser:', err);
        const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to load samples. Please try again.';
        setSamplesError(errorMessage);
        setSamples([]);
        setSamplesMeta({ total: 0, loading: false });
      } finally {
        // no-op: loading flag managed via samplesMeta
      }
    };

    fetchSamples();
  }, [
    isExplainabilityActive,
    selectedModelIds,
    selectedModelForSamples,
    currentWaterfallModel,
    explainabilityDataSource,
    samplesPage,
    samplesSearchQuery,
  ]);

  // Auto-select first sample when samples are loaded and no sample is selected
  // This ensures waterfall shows sample values on initial load and when toggling test/train
  useEffect(() => {
    if (!isExplainabilityActive) return;
    if (samples.length > 0 && selectedSampleIndex === null) {
      // Auto-select the first sample to show its values in the waterfall
      setSelectedSampleIndex(samples[0].sample_index);
    } else if (samples.length === 0 && selectedSampleIndex !== null) {
      // Reset selection if no samples are available
      setSelectedSampleIndex(null);
    }
  }, [samples, selectedSampleIndex, isExplainabilityActive]);

  // Fetch evaluation data (without explainability) for selected models.
  // IMPORTANT: we preserve any previously-loaded explainability_data so that
  // explainability charts remain available when returning to this step.
  useEffect(() => {
    if (selectedModelIds.length === 0) {
      // If no models selected, clear loading state
      if (isExplainabilityActive) {
        setLoading(false);
      }
      return;
    }
    
    // Check if we already have evaluation data for all models
    // But don't early return on explainability tab if explainability data is missing
    const hasAllEvaluationData = selectedModelIds.length > 0 && selectedModelIds.every(id => evaluationData[id]);
    if (hasAllEvaluationData) {
      if (isExplainabilityActive) {
        // On explainability tab, check if we also have explainability data
        // Use all selectedModelIds for explainability (don't filter segmented models)
        const hasAllExplainabilityData = selectedModelIds.every(id => {
          const data = evaluationData[id];
          return data?.explainability_data && data.explainability_data.length > 0;
        });
        if (hasAllExplainabilityData) {
          // Have both evaluation and explainability data, safe to return
          setLoading(false);
          return;
        }
        // Have evaluation data but missing explainability data - clear loading and let lazy loading handle it
        setLoading(false);
        return;
      }
      // Not on explainability tab, safe to return if we have evaluation data
      setLoading(false);
      return;
    }

    const fetchEvaluationData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Explainability tab supports both global and segmented models
        const modelsToFetch = selectedModelIds;

        const results = await Promise.all(
          modelsToFetch.map(async (modelId) => {
            try {
              const response = await modelEvaluationService.getModelEvaluation(modelId, false);
              return { modelId, data: response.evaluation_data };
            } catch (err: any) {
              console.error(`Error fetching evaluation for ${modelId}:`, err);
              return {
                modelId,
                error: err.response?.data?.detail || 'Failed to fetch evaluation data',
              };
            }
          }),
        );

        const freshMap: Record<string, ModelEvaluationData> = {};
        const errors: string[] = [];

        results.forEach((result) => {
          if ((result as any).data) {
            freshMap[result.modelId] = (result as any).data;
          } else if ((result as any).error) {
            errors.push(`${result.modelId}: ${(result as any).error}`);
          }
        });

        // Merge fresh evaluation data with any existing cached entries,
        // preserving previously-loaded explainability_data where present.
        // Also track which models need explainabilityDataLoaded cleared
        const modelsToClearFromLoaded: string[] = [];
        setEvaluationData((prev) => {
          const merged: Record<string, ModelEvaluationData> = { ...prev };
          
          Object.entries(freshMap).forEach(([modelId, fresh]) => {
            const existing = prev[modelId];
            if (existing?.explainability_data && (!fresh.explainability_data || fresh.explainability_data.length === 0)) {
              merged[modelId] = {
                ...fresh,
                explainability_data: existing.explainability_data,
              };
            } else {
              merged[modelId] = fresh;
              // If fresh evaluation data doesn't have explainability_data, mark it for clearing from loaded set
              // This allows lazy loading to fetch explainability data for new/updated models
              if ((!fresh.explainability_data || fresh.explainability_data.length === 0)) {
                modelsToClearFromLoaded.push(modelId);
              }
            }
          });
          return merged;
        });
        
        // Clear explainabilityDataLoaded for models that got fresh evaluation data without explainability_data
        // This allows lazy loading to fetch explainability data for new/updated models
        if (modelsToClearFromLoaded.length > 0) {
          setExplainabilityDataLoaded((prevLoaded) => {
            const newSet = new Set(prevLoaded);
            modelsToClearFromLoaded.forEach((modelId) => {
              newSet.delete(modelId);
            });
            return newSet;
          });
        }

        if (Object.keys(freshMap).length === 0 && selectedModelIds.length > 0) {
          setError(
            `Failed to load evaluation data for all ${selectedModelIds.length} selected model(s). They may not have MEEA evaluation data yet.`,
          );
        }
      } catch (err) {
        console.error('Error fetching evaluation data for AI Explainability:', err);
        setError('Failed to fetch evaluation data for one or more models');
      } finally {
        setLoading(false);
      }
    };

    fetchEvaluationData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModelIds.join(','), activeTab, availableModels.length]);

  // Lazy load explainability data when Explainability tab is active
  useEffect(() => {
    if (!isExplainabilityActive || selectedModelIds.length === 0) {
      // If not on explainability tab or no models selected, clear loading state
      if (!isExplainabilityActive) {
        setLoadingExplainability(false);
      }
      return;
    }
    // Skip loading if we're refreshing explainability (to prevent hiding content)
    if (isRefreshingExplainabilityRef.current) return;

    const modelsToLoad = selectedModelIds.filter((id) => {
      // Check if evaluation data exists - if not, we can't load explainability data yet
      const data = evaluationData[id];
      if (!data) {
        return false; // Wait for evaluation data first
      }
      
      // Check if explainability_data exists at all
      if (!data.explainability_data || data.explainability_data.length === 0) {
        // No explainability data - need to load it
        // Always try to load if explainability_data is missing, regardless of explainabilityDataLoaded
        // This ensures new models get their explainability data loaded immediately
        return true;
      }
      
      // Filter by current data source
      const hasDataForCurrentSource = data.explainability_data.some((d: any) => {
        let dataSource = d.data_source;
        if (dataSource === null || dataSource === undefined || dataSource === 'null' || dataSource === '') {
          dataSource = 'test';
        }
        dataSource = String(dataSource).trim().toLowerCase();
        const targetSource = String(explainabilityDataSource).trim().toLowerCase();
        return dataSource === targetSource && 
               (d.data_type === 'shap_summary' || d.data_type === 'pdp' || d.data_type === 'shap_waterfall');
      });
      
      // Need to load if missing data for current source
      // Check explainabilityDataLoaded to prevent duplicate loads for the same data source
      return !hasDataForCurrentSource && !explainabilityDataLoaded.has(id);
    });

    if (modelsToLoad.length === 0) {
      // No models need loading, ensure loading state is cleared
      setLoadingExplainability(false);
      return;
    }

    // Set loading state immediately when we detect data needs to be loaded
    setLoadingExplainability(true);

    const fetchExplainabilityData = async () => {
      try {
        const results = await Promise.allSettled(
          modelsToLoad.map(async (modelId) => {
            try {
              const explainabilityData = await modelEvaluationService.getExplainabilityData(modelId);

              // Check for data for the CURRENT data source (train or test)
              const hasDataForCurrentSource = explainabilityData.some((d: any) => {
                let ds =
                  d.data_source === null || d.data_source === undefined || d.data_source === ''
                    ? 'test'
                    : String(d.data_source).toLowerCase();
                ds = ds.trim().toLowerCase();
                const targetSource = String(explainabilityDataSource).trim().toLowerCase();
                return (
                  ds === targetSource &&
                  (d.data_type === 'shap_summary' || d.data_type === 'pdp' || d.data_type === 'shap_waterfall')
                );
              });

              if (hasDataForCurrentSource) {
                return { modelId, data: explainabilityData };
              } else {
                // Recalculate for the current data source
                await modelEvaluationService.recalculateExplainability(modelId, explainabilityDataSource);
                const response = await modelEvaluationService.getModelEvaluation(modelId, true);
                return { modelId, data: response.evaluation_data.explainability_data };
              }
            } catch (err: any) {
              console.error(`Error loading/calculating explainability for ${modelId}:`, err);
              return {
                modelId,
                error: err.response?.data?.detail || 'Failed to load/calculate explainability data',
              };
            }
          }),
        );

        setEvaluationData((prev) => {
          const updated = { ...prev };
          results.forEach((result) => {
            if (result.status === 'fulfilled' && (result.value as any).data) {
              const { modelId, data } = result.value as any;
              if (updated[modelId]) {
                updated[modelId] = {
                  ...updated[modelId],
                  explainability_data: data,
                };
              }
            }
          });
          return updated;
        });

        setExplainabilityDataLoaded((prev) => {
          const newSet = new Set(prev);
          results.forEach((result) => {
            if (result.status === 'fulfilled' && (result.value as any).data) {
              newSet.add((result.value as any).modelId);
            }
          });
          return newSet;
        });
      } finally {
        setLoadingExplainability(false);
      }
    };

    fetchExplainabilityData();
  }, [activeTab, selectedModelIds, explainabilityDataLoaded, evaluationData, explainabilityDataSource]);

  // Polling for background recalculations (copied from ModelEvaluationMEEA)
  useEffect(() => {
    if (!isExplainabilityActive || selectedModelIds.length === 0) return;

    const pendingModelIds = Object.entries(recalculatingExplainabilityRef.current)
      .filter(([_, dataSource]) => dataSource === explainabilityDataSourceRef.current)
      .map(([modelId]) => modelId);

    if (pendingModelIds.length === 0) {
      return;
    }

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    pollIntervalRef.current = setInterval(async () => {
      const currentPendingIds = Object.entries(recalculatingExplainabilityRef.current)
        .filter(([_, dataSource]) => dataSource === explainabilityDataSourceRef.current)
        .map(([modelId]) => modelId);

      if (currentPendingIds.length === 0) {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        return;
      }

      const checkPromises = currentPendingIds.map(async (modelId) => {
        try {
          const explainabilityData = await modelEvaluationService.getExplainabilityData(modelId);

          const currentDataSource = explainabilityDataSourceRef.current;
          const hasData = explainabilityData.some((d: any) => {
            const ds =
              d.data_source === null || d.data_source === undefined || d.data_source === ''
                ? 'test'
                : String(d.data_source).toLowerCase();
            const targetDs = String(currentDataSource).toLowerCase();
            return ds === targetDs && (d.data_type === 'shap_summary' || d.data_type === 'pdp' || d.data_type === 'shap_waterfall');
          });

          if (hasData) {
            const response = await modelEvaluationService.getModelEvaluation(modelId, true);
            setEvaluationData((prev) => ({
              ...prev,
              [modelId]: response.evaluation_data,
            }));

            setRecalculatingExplainability((prev) => {
              const newState = { ...prev };
              if (newState[modelId] === currentDataSource) {
                delete newState[modelId];
              }
              return newState;
            });

            return true;
          }

          return false;
        } catch (err) {
          console.error(`Error polling for model ${modelId}:`, err);
          return false;
        }
      });

      const results = await Promise.all(checkPromises);
      const allLoaded = results.every((r) => r === true) && currentPendingIds.length > 0;

      if (allLoaded) {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    }, 5000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [activeTab, selectedModelIds, explainabilityDataSource]);

  const hasExplainabilityData = (modelId: string, dataSource: 'train' | 'test'): boolean => {
    const data = evaluationData[modelId];
    if (!data?.explainability_data) return false;

    return data.explainability_data.some((d: any) => {
      const ds =
        d.data_source === null || d.data_source === undefined || d.data_source === 'null' || d.data_source === ''
          ? 'test'
          : String(d.data_source).toLowerCase();
      const targetDs = String(dataSource).toLowerCase();
      return ds === targetDs && (d.data_type === 'shap_summary' || d.data_type === 'pdp' || d.data_type === 'shap_waterfall');
    });
  };

  const handleExplainabilityDataSourceToggle = async (newDataSource: 'train' | 'test') => {
    if (newDataSource === explainabilityDataSource) return;

    setExplainabilityDataSource(newDataSource);

    const modelsToRecalculate = selectedModelIds.filter((id) => {
      if (recalculatingExplainability[id] === newDataSource) {
        return false;
      }
      const hasData = evaluationData[id] && hasExplainabilityData(id, newDataSource);
      return !hasData && evaluationData[id];
    });

    if (modelsToRecalculate.length === 0) {
      return;
    }

    setRecalculatingExplainability((prev) => {
      const newState = { ...prev };
      modelsToRecalculate.forEach((id) => {
        newState[id] = newDataSource;
      });
      return newState;
    });

    modelsToRecalculate.forEach(async (modelId) => {
      try {
        await modelEvaluationService.recalculateExplainability(modelId, newDataSource);
        const response = await modelEvaluationService.getModelEvaluation(modelId, true);
        setEvaluationData((prev) => ({
          ...prev,
          [modelId]: response.evaluation_data,
        }));
        setRecalculatingExplainability((prev) => {
          const newState = { ...prev };
          if (newState[modelId] === newDataSource) {
            delete newState[modelId];
            recalculatingExplainabilityRef.current = newState;
          }
          return newState;
        });
      } catch (err) {
        console.error(`Error recalculating explainability for ${modelId}:`, err);
        setRecalculatingExplainability((prev) => {
          const newState = { ...prev };
          if (newState[modelId] === newDataSource) {
            delete newState[modelId];
          }
          return newState;
        });
      }
    });
  };

  // Handler to refresh models and evaluation data (for header button)
  const handleRefreshModels = async () => {
    await fetchModels();
  };

  // Handler to refresh explainability data only (for explainability tab button)
  const handleRefreshExplainability = async () => {
    // Set flag to prevent explainability loading effect from hiding content
    isRefreshingExplainabilityRef.current = true;
    
    try {
      // First, refresh the model list to pick up newly trained models
      // But do it without triggering loading states that hide content
      if (datasetId) {
        const response = await modelEvaluationService.listModelsByDataset(datasetId);
        const allModels = response.models || [];
        const modelsWithMEEA = allModels.filter((m: any) => m.has_meea_data === true);
        const sortedModels = modelsWithMEEA.sort((a, b) => {
          const dateA = new Date(a.created_at || a.training_date || 0).getTime();
          const dateB = new Date(b.created_at || b.training_date || 0).getTime();
          return dateB - dateA;
        });
        
        setAvailableModels(sortedModels);
        const allModelIds = sortedModels.map((m: EvaluationModel) => m.id);
        // Auto-select all models, preserving existing selections and adding new ones
        setSelectedModelIds((prev) => {
          const existingSelected = prev.filter(id => sortedModels.some(m => m.id === id));
          const newModels = allModelIds.filter(id => !prev.includes(id));
          return newModels.length > 0 ? [...existingSelected, ...newModels] : (prev.length > 0 ? prev : allModelIds);
        });
      }
    } catch (err) {
      console.error('Error refreshing models:', err);
      // Continue with explainability refresh even if model refresh fails
    }
    
    // First, ensure evaluationData exists for all selected models
    // Fetch evaluation data for models that don't have it yet
    const modelsNeedingEvaluationData = selectedModelIds.filter((id) => !evaluationData[id]);
    let freshEvaluationData: Record<string, ModelEvaluationData> = {};
    
    if (modelsNeedingEvaluationData.length > 0) {
      try {
        const results = await Promise.all(
          modelsNeedingEvaluationData.map(async (modelId) => {
            try {
              const response = await modelEvaluationService.getModelEvaluation(modelId, false);
              return { modelId, data: response.evaluation_data };
            } catch (err: any) {
              console.error(`Error fetching evaluation for ${modelId}:`, err);
              return {
                modelId,
                error: err.response?.data?.detail || 'Failed to fetch evaluation data',
              };
            }
          }),
        );

        results.forEach((result) => {
          if ((result as any).data) {
            freshEvaluationData[result.modelId] = (result as any).data;
          }
        });

        // Update evaluationData with fetched data
        if (Object.keys(freshEvaluationData).length > 0) {
          setEvaluationData((prev) => {
            const merged: Record<string, ModelEvaluationData> = { ...prev };
            Object.entries(freshEvaluationData).forEach(([modelId, fresh]) => {
              merged[modelId] = fresh;
            });
            return merged;
          });
        }
      } catch (err) {
        console.error('Error fetching evaluation data during refresh:', err);
      }
    }
    
    // Merge fresh evaluationData with existing for filtering
    const mergedEvaluationData = { ...evaluationData, ...freshEvaluationData };
    
    // Then refresh explainability data for selected models
    // Use merged evaluationData to include freshly fetched data
    const modelsToRecalculate = selectedModelIds.filter((id) => {
      // Skip if still no evaluationData (model might not have MEEA data yet)
      if (!mergedEvaluationData[id]) {
        return false;
      }
      // Skip if already recalculating for this data source
      if (recalculatingExplainability[id] === explainabilityDataSource) {
        return false;
      }
      return true;
    });

    if (modelsToRecalculate.length === 0) {
      isRefreshingExplainabilityRef.current = false;
      return;
    }

    setRecalculatingExplainability((prev) => {
      const newState = { ...prev };
      modelsToRecalculate.forEach((id) => {
        // Mark as recalculating for both train and test
        // Use a special marker or just mark for current source - the UI will show loading
        newState[id] = explainabilityDataSource;
      });
      return newState;
    });

    // Recalculate explainability for BOTH train and test data sources for new models
    // This ensures PDP data is available for both sources
    const dataSourcesToRecalculate: ('train' | 'test')[] = ['train', 'test'];
    
    modelsToRecalculate.forEach(async (modelId) => {
      try {
        // Recalculate for both train and test to ensure all data is available
        const recalculationPromises = dataSourcesToRecalculate.map(async (dataSource) => {
          await modelEvaluationService.recalculateExplainability(modelId, dataSource);
        });
        
        await Promise.all(recalculationPromises);
        
        // Fetch the updated evaluation data with all explainability data
        const response = await modelEvaluationService.getModelEvaluation(modelId, true);
        setEvaluationData((prev) => ({
          ...prev,
          [modelId]: response.evaluation_data,
        }));
        
        // Clear from explainabilityDataLoaded to allow lazy loading to detect new data
        setExplainabilityDataLoaded((prevLoaded) => {
          const newSet = new Set(prevLoaded);
          newSet.delete(modelId);
          return newSet;
        });
        
        setRecalculatingExplainability((prev) => {
          const newState = { ...prev };
          // Clear recalculating state for both train and test
          delete newState[modelId];
          recalculatingExplainabilityRef.current = newState;
          // Clear refresh flag when all models are done
          if (Object.keys(newState).length === 0) {
            isRefreshingExplainabilityRef.current = false;
          }
          return newState;
        });
      } catch (err) {
        console.error(`Error refreshing explainability for ${modelId}:`, err);
        setRecalculatingExplainability((prev) => {
          const newState = { ...prev };
          delete newState[modelId];
          // Clear refresh flag when all models are done (even on error)
          if (Object.keys(newState).length === 0) {
            isRefreshingExplainabilityRef.current = false;
          }
          return newState;
        });
      }
    });
  };

  const comparisonModels = useMemo(() => {
    return Object.entries(evaluationData).map(([modelId, data]) => {
      const model = availableModels.find((m) => m.id === modelId) || data.model;
      const metrics = data.performance_metrics;

      return {
        modelName: model?.name || data.model?.name || 'Unknown Model',
        modelId,
        accuracy: metrics?.accuracy || 0,
        precision: metrics?.precision || 0,
        recall: metrics?.recall || 0,
        f1Score: metrics?.f1_score || 0,
        aucRoc: metrics?.auc_roc || 0,
        aucPr: metrics?.auc_pr,
        logLoss: metrics?.log_loss,
        color: '#3B82F6',
      };
    });
  }, [evaluationData, availableModels]);

  // Comparison models for display (all models, including segmented)
  const globalComparisonModels = useMemo(() => {
    return comparisonModels.filter((model) => {
      const modelInfo = availableModels.find(m => m.id === model.modelId);
      // Only include models that are NOT segmented models
      return !modelInfo || !(modelInfo as any).is_segment_model;
    });
  }, [comparisonModels, availableModels]);

  const modelsCount = comparisonModels.length;

  if (loading && modelsCount === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl shadow-sm">
      {/* Compact header: only status & refresh models, no title/description */}
      <div className="border-b border-gray-200 dark:border-gray-800 px-6 py-3 flex items-center justify-end gap-3">
        <span className="px-3 py-1 bg-blue-50 text-blue-700 dark:bg-gray-800 dark:text-white rounded-full text-xs font-semibold">
          {modelsCount} Models Evaluated
        </span>
        <button
          type="button"
          onClick={handleRefreshModels}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-white text-xs border border-gray-200 dark:border-gray-700"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh Models</span>
        </button>
      </div>

      {/* Explainability controls shared across Shap / PDP views */}
      {modelsCount > 0 && (
        <div className="border-b border-gray-100 dark:border-gray-800 px-6 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-gray-700 dark:text-white">Data Source:</span>
            <button
              type="button"
              onClick={() =>
                handleExplainabilityDataSourceToggle(
                  explainabilityDataSource === 'test' ? 'train' : 'test',
                )
              }
              className={`
                relative inline-flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium text-xs transition-all
                ${
                  explainabilityDataSource === 'test'
                  ? 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-gray-800 dark:text-white'
                  : 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-gray-800 dark:text-white'
                }
              `}
            >
              {Object.values(recalculatingExplainability).some(
                (v) => v === explainabilityDataSource,
              ) && <Loader2 className="w-3 h-3 animate-spin" />}
              {explainabilityDataSource === 'test' ? (
                <>
                  <span>Test</span>
                  <ToggleLeft className="w-4 h-4" />
                </>
              ) : (
                <>
                  <span>Train</span>
                  <ToggleRight className="w-4 h-4" />
                </>
              )}
            </button>
            <span className="text-xs text-gray-500 dark:text-white">
              {explainabilityDataSource === 'test'
                ? 'Showing explainability on test data'
                : 'Showing explainability on training data'}
            </span>
          </div>

          <button
            type="button"
            onClick={handleRefreshExplainability}
            disabled={Object.values(recalculatingExplainability).some(
              (v) => v === explainabilityDataSource,
            )}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-white text-xs border border-gray-200 dark:border-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw
              className={`w-4 h-4 ${
                Object.values(recalculatingExplainability).some(
                  (v) => v === explainabilityDataSource,
                )
                  ? 'animate-spin'
                  : ''
              }`}
            />
            <span>Refresh Explainability</span>
          </button>
        </div>
      )}

      {/* Shap / PDP Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800 px-6">
        <nav className="flex space-x-6">
          {[
            { id: 'shap', icon: FileText, label: 'Shap' },
            { id: 'pdp', icon: FileText, label: 'Pdp / Ice Lines' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as ExplainabilityTabId)}
                className={`
                  flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors
                  ${
                    isActive
                      ? 'border-blue-500 text-blue-600 dark:text-white'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-white dark:hover:text-white dark:hover:border-gray-600'
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Error */}
      {error && (
        <div className="px-6 py-4">
          <div className="bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/30 dark:border-red-800 dark:text-red-200 px-4 py-3 rounded-lg flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <div className="text-sm">{error}</div>
          </div>
        </div>
      )}

      {/* Loading indicator when fetching models/evaluation data on explainability tab */}
      {loading && isExplainabilityActive && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
          <span className="ml-3 text-sm text-gray-600 dark:text-white">Loading models and evaluation data...</span>
        </div>
      )}

      {/* No models */}
      {!loading && modelsCount === 0 && (
        <div className="px-6 py-10 text-center text-sm text-gray-600 dark:text-white">
          No models with evaluation data found for this dataset. Please train and evaluate models first.
        </div>
      )}

      {/* Explainability content */}
      {!loading && modelsCount > 0 && isExplainabilityActive && (
        <div className="px-6 py-6 space-y-4">
          <ExplainabilityTab
            availableModels={availableModels}
            selectedModelIds={selectedModelIds}
            evaluationData={evaluationData}
            explainabilityDataSource={explainabilityDataSource}
            recalculatingExplainability={recalculatingExplainability}
            loadingExplainability={loadingExplainability}
            initialLoading={loading}
            samples={samples}
            samplesTotal={samplesMeta.total}
            samplesLoading={samplesMeta.loading}
            selectedSampleIndex={selectedSampleIndex}
            onSelectSample={(sampleIndex) => setSelectedSampleIndex(sampleIndex)}
            samplesPage={samplesPage}
            samplesPageSize={SAMPLES_PAGE_SIZE}
            onChangeSamplesPage={setSamplesPage}
            initialSearchQuery={samplesSearchQuery}
            onApplySearch={(query) => setSamplesSearchQuery(query)}
            samplesError={samplesError}
            onModelSelectedForSamples={(modelId: string) => setSelectedModelForSamples(modelId)}
            selectedWaterfallModel={currentWaterfallModel || selectedModelIds[0]}
            onWaterfallModelChange={(modelId: string | null) => setCurrentWaterfallModel(modelId)}
            samplesModelId={samplesModelId}
            samplesTargetColumn={samplesTargetColumn}
            viewMode={activeTab}
          />
        </div>
      )}

    </div>
  );
};

export default Step8AIExplainabilityAndDiagnostics;



