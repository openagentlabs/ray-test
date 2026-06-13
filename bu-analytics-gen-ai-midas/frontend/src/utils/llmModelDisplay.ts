const PROVIDER_DISPLAY: Record<string, string> = {
  azure: 'Azure',
  azure_ai: 'Azure',
  'azure/gpt5_series': 'Azure',
  'azure/responses': 'Azure',
  bedrock: 'AWS',
  openai: 'OpenAI',
};

const MODEL_LABEL_OVERRIDES: Record<string, string> = {
  'gpt-4.1-mini': 'GPT-4.1-Mini',
  'gpt-4.1-nano': 'GPT-4.1-Nano',
  'gpt-5-mini': 'GPT-5-Mini',
  'gpt-5-nano': 'GPT-5-Nano',
  'gpt-5.1-codex-mini': 'GPT-5.1-Codex-Mini',
  'gpt-5.2-codex': 'GPT-5.2-Codex',
  'gpt-5.3-codex': 'GPT-5.3-Codex',
  'gpt-5.4-mini': 'GPT-5.4-Mini',
  'gpt-5.4-nano': 'GPT-5.4-Nano',
  'claude-haiku-4-5': 'Claude Haiku 4.5',
  'claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'claude-opus-4-6': 'Claude Opus 4.6',
  'anthropic.claude-haiku-4-5': 'Claude Haiku 4.5',
  'anthropic.claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'anthropic.claude-opus-4-6': 'Claude Opus 4.6',
  'google.gemma-3-27b-it': 'Gemma 3 27B',
  'amazon.nova-pro-v1:0': 'Amazon Nova Pro',
  'text-embedding-ada-002': 'Text Embedding Ada 002',
  'amazon.titan-embed-text-v2:0': 'Titan Embed Text V2',
};

export function formatProviderDisplay(provider: string): string {
  return PROVIDER_DISPLAY[provider] ?? provider;
}

export function formatModelLabel(id: string, provider: string): string {
  const label = MODEL_LABEL_OVERRIDES[id] ?? id;
  const providerDisplay = formatProviderDisplay(provider);
  return `${label} - ${providerDisplay}`;
}
