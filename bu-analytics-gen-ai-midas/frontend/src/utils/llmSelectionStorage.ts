export type LlmSelection = {
  chat?: string;
  knowledge_graph?: string;
  embedding?: string;
};

const STORAGE_KEY = 'llm_selection';

export const loadLlmSelection = (): LlmSelection | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed as LlmSelection;
  } catch {
    return null;
  }
};

export const saveLlmSelection = (selection: LlmSelection) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selection));
  } catch {
    // ignore storage errors
  }
};

export const getLlmSelectionHeaders = (): Record<string, string> => {
  const selection = loadLlmSelection();
  if (!selection) return {};

  const headers: Record<string, string> = {};
  if (selection.chat) headers['X-LLM-Chat-Model'] = selection.chat;
  if (selection.knowledge_graph) headers['X-LLM-KG-Model'] = selection.knowledge_graph;
  if (selection.embedding) headers['X-LLM-Embedding-Model'] = selection.embedding;
  return headers;
};
