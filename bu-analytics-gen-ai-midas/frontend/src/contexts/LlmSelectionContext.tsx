import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { fastApiService } from '../services/fastApiService';
import { loadLlmSelection, saveLlmSelection, LlmSelection } from '../utils/llmSelectionStorage';

type ModelMapping = Record<string, {
  provider: string;
  model: string;
  api_base?: string;
  api_version?: string;
  reasoning_effort?: string;
}>;

type LockedState = {
  locked: boolean;
  model_id?: string | null;
};

type LlmModelsResponse = {
  models: {
    chat: ModelMapping;
    knowledge_graph: ModelMapping;
    embedding: ModelMapping;
  };
  defaults: {
    chat: string;
    knowledge_graph: string;
    embedding: string;
  };
  locked_by_env: {
    chat: LockedState;
    knowledge_graph: LockedState;
    embedding: LockedState;
  };
};

type LlmSelectionContextValue = {
  loading: boolean;
  models: LlmModelsResponse['models'] | null;
  defaults: LlmModelsResponse['defaults'] | null;
  lockedByEnv: LlmModelsResponse['locked_by_env'] | null;
  selection: LlmSelection;
  setChatModelId: (modelId: string) => void;
  setKgModelId: (modelId: string) => void;
  setEmbeddingModelId: (modelId: string) => void;
  isObjectivesStep: boolean;
  setIsObjectivesStep: (value: boolean) => void;
};

const LlmSelectionContext = createContext<LlmSelectionContextValue | null>(null);

const validateModelSelection = (
  selection: LlmSelection,
  models: LlmModelsResponse['models'],
  defaults: LlmModelsResponse['defaults']
): LlmSelection => {
  const next = { ...selection };
  if (!models.chat[next.chat || '']) next.chat = defaults.chat;
  if (!models.knowledge_graph[next.knowledge_graph || '']) next.knowledge_graph = defaults.knowledge_graph;
  if (!models.embedding[next.embedding || '']) next.embedding = defaults.embedding;
  return next;
};

export const LlmSelectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<LlmModelsResponse['models'] | null>(null);
  const [defaults, setDefaults] = useState<LlmModelsResponse['defaults'] | null>(null);
  const [lockedByEnv, setLockedByEnv] = useState<LlmModelsResponse['locked_by_env'] | null>(null);
  const [selection, setSelection] = useState<LlmSelection>({});
  const [isObjectivesStep, setIsObjectivesStep] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fastApiService.getLLMModels();
      const data = response as LlmModelsResponse;
      setModels(data.models);
      setDefaults(data.defaults);
      setLockedByEnv(data.locked_by_env);

      const stored = loadLlmSelection() || {};
      const validated = validateModelSelection(stored, data.models, data.defaults);
      const lockedSelection = { ...validated };
      if (data.locked_by_env.chat?.locked && data.locked_by_env.chat.model_id) {
        lockedSelection.chat = data.locked_by_env.chat.model_id;
      }
      if (data.locked_by_env.knowledge_graph?.locked && data.locked_by_env.knowledge_graph.model_id) {
        lockedSelection.knowledge_graph = data.locked_by_env.knowledge_graph.model_id;
      }
      if (data.locked_by_env.embedding?.locked && data.locked_by_env.embedding.model_id) {
        lockedSelection.embedding = data.locked_by_env.embedding.model_id;
      }
      setSelection(lockedSelection);
      saveLlmSelection(lockedSelection);
    } catch (err) {
      console.warn('Failed to load LLM models:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const updateSelection = useCallback((partial: LlmSelection) => {
    setSelection(prev => {
      const next = { ...prev, ...partial };
      saveLlmSelection(next);
      return next;
    });
  }, []);

  const value = useMemo<LlmSelectionContextValue>(() => ({
    loading,
    models,
    defaults,
    lockedByEnv,
    selection,
    setChatModelId: (modelId: string) => updateSelection({ chat: modelId }),
    setKgModelId: (modelId: string) => updateSelection({ knowledge_graph: modelId }),
    setEmbeddingModelId: (modelId: string) => updateSelection({ embedding: modelId }),
    isObjectivesStep,
    setIsObjectivesStep,
  }), [loading, models, defaults, lockedByEnv, selection, updateSelection, isObjectivesStep]);

  return (
    <LlmSelectionContext.Provider value={value}>
      {children}
    </LlmSelectionContext.Provider>
  );
};

export const useLlmSelection = () => {
  const ctx = useContext(LlmSelectionContext);
  if (!ctx) {
    throw new Error('useLlmSelection must be used within LlmSelectionProvider');
  }
  return ctx;
};
