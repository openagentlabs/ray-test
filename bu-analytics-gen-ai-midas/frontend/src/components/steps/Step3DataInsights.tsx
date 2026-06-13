import React, { useEffect, useRef, useState } from 'react';
import { Check, Lightbulb, Loader2, AlertTriangle, Sparkles, ListChecks } from 'lucide-react';
import DataSplit from '../DataSplit';
import UserKnowledgeUploadPanel from '../UserKnowledgeUploadPanel';

type DataScopeLabel = 'entire' | 'train' | 'test' | 'validation';

function readInsightsDataScopeFromSession(): DataScopeLabel {
  try {
    const raw = sessionStorage.getItem('dataset_config');
    if (!raw) return 'entire';
    const parsed = JSON.parse(raw) as { data_scope?: string };
    const s = parsed?.data_scope;
    if (s === 'train' || s === 'test' || s === 'validation' || s === 'entire') return s;
  } catch {
    /* ignore */
  }
  return 'entire';
}

function scopeDisplayLabel(scope: DataScopeLabel): string {
  switch (scope) {
    case 'entire':
      return 'Full dataset';
    case 'train':
      return 'Train';
    case 'test':
      return 'Test';
    case 'validation':
      return 'Validation';
    default:
      return 'Full dataset';
  }
}

export type AutoInsightStepStatus = 'idle' | 'running' | 'done' | 'absent' | 'error';

const AUTO_INSIGHT_CHECKLIST: { id: string; label: string }[] = [
  { id: 'bivariate_analysis', label: 'Bivariate Analysis' },
  { id: 'correlation_analysis', label: 'Correlation analysis' },
  { id: 'iv_analysis', label: 'Information Value (IV)' },
  { id: 'variance_inflation_factor', label: 'Variance Inflation Factor (VIF)' },
  { id: 'correlation_matrix', label: 'Correlation Matrix' },
  { id: 'correlation_ratio_analysis', label: 'Correlation ratio (η)' },
];

interface Step3DataInsightsProps {
  // Data insights functionality states
  selectedInsightSteps: string[];
  setSelectedInsightSteps: (steps: string[]) => void;
  
  // Insight handlers
  onAutoDataInsights: () => Promise<void>;
  onStandardDataInsights: (stepsOverride?: string[]) => Promise<void>;
  onInsightStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
  
  // Dataset info for Data Split
  activeDatasetId?: string | null;
  datasetAnalysis?: {
    totalRows: number;
  } | null;
  /** Shown in Auto Insights context strip; insights use the active target from configuration */
  targetVariable?: string | null;

  autoInsightStepStatus: Record<string, AutoInsightStepStatus>;

  insightsMode: 'auto' | 'standard';
  onInsightsModeChange: (mode: 'auto' | 'standard') => void;
}

const Step3DataInsights: React.FC<Step3DataInsightsProps> = ({
  selectedInsightSteps,
  setSelectedInsightSteps,
  onAutoDataInsights,
  onStandardDataInsights,
  onInsightStepToggle,
  renderStepChat,
  activeDatasetId,
  datasetAnalysis,
  targetVariable,
  autoInsightStepStatus,
  insightsMode,
  onInsightsModeChange
}) => {
  /** How many analysis rows to show; they appear after Auto Insights starts (parallel runs show all rows). */
  const [autoInsightVisibleRows, setAutoInsightVisibleRows] = useState(0);
  /** Only true after the user clicks "Generate Auto Insights" — hides the list until then (even if parent state was non-idle). */
  const [autoInsightStartedByClick, setAutoInsightStartedByClick] = useState(false);
  const [dataScope, setDataScope] = useState<DataScopeLabel>(() =>
    typeof window !== 'undefined' ? readInsightsDataScopeFromSession() : 'entire'
  );
  const staggerTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'dataset_config' || e.key === null) setDataScope(readInsightsDataScopeFromSession());
    };
    const onScope = (e: Event) => {
      const d = (e as CustomEvent<{ scope?: string }>).detail;
      const s = d?.scope;
      if (s === 'train' || s === 'test' || s === 'validation' || s === 'entire') setDataScope(s);
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener('datasetScopeChanged', onScope as EventListener);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('datasetScopeChanged', onScope as EventListener);
    };
  }, []);

  const clearStaggerTimer = () => {
    if (staggerTimerRef.current) {
      clearInterval(staggerTimerRef.current);
      staggerTimerRef.current = null;
    }
  };

  useEffect(() => {
    const statuses = AUTO_INSIGHT_CHECKLIST.map((r) => autoInsightStepStatus[r.id] ?? 'idle');
    const allIdle = statuses.every((s) => s === 'idle');
    if (allIdle) {
      clearStaggerTimer();
      setAutoInsightVisibleRows(0);
      setAutoInsightStartedByClick(false);
      return;
    }

    // Parallel API runs: show all checklist rows so each line can flip running → done/error independently
    clearStaggerTimer();
    setAutoInsightVisibleRows(AUTO_INSIGHT_CHECKLIST.length);
  }, [autoInsightStepStatus]);

  const autoInsightAllRunning = AUTO_INSIGHT_CHECKLIST.every(
    (r) => (autoInsightStepStatus[r.id] ?? 'idle') === 'running'
  );
  const anyAutoInsightActivity = AUTO_INSIGHT_CHECKLIST.some(
    (r) => (autoInsightStepStatus[r.id] ?? 'idle') !== 'idle'
  );
  /** Button click or parent-triggered auto run; show once rows are visible or all lines are running. */
  const showAutoInsightProgress =
    (autoInsightStartedByClick || anyAutoInsightActivity) &&
    (autoInsightVisibleRows > 0 || autoInsightAllRunning);

  const statusList = AUTO_INSIGHT_CHECKLIST.map((r) => autoInsightStepStatus[r.id] ?? 'idle');
  const completedCount = statusList.filter((s) => s === 'done' || s === 'absent').length;
  const errorCount = statusList.filter((s) => s === 'error').length;
  const anyRunning = statusList.some((s) => s === 'running');
  const allTerminal = statusList.every((s) => s === 'done' || s === 'absent' || s === 'error');
  const allDoneSuccess = statusList.every((s) => s === 'done' || s === 'absent');

  const datasetReady = !!activeDatasetId;
  const targetOk = !!(targetVariable && String(targetVariable).trim());
  const canStartAuto = datasetReady && targetOk && !anyRunning;

  return (
    <div className="space-y-6">
      {/* Data Split Component */}
      <DataSplit activeDatasetId={activeDatasetId} datasetAnalysis={datasetAnalysis} stepKey={3} showSamplingUI={false} />

      <UserKnowledgeUploadPanel datasetId={activeDatasetId || null} scope="data_insights" />

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white shrink-0">Data Insights</h3>
          <div
            className="inline-flex w-full sm:w-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 p-1 shadow-[inset_0_1px_2px_rgba(0,0,0,0.06)] dark:shadow-[inset_0_1px_2px_rgba(0,0,0,0.25)]"
            role="tablist"
            aria-label="Insights mode"
          >
            <button
              type="button"
              role="tab"
              aria-selected={insightsMode === 'auto'}
              id="insights-mode-auto"
              onClick={() => onInsightsModeChange('auto')}
              className={`flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all sm:min-w-[11rem] ${
                insightsMode === 'auto'
                  ? 'bg-blue-600 text-white shadow-sm ring-1 ring-blue-600/20 dark:ring-blue-400/20'
                  : 'text-gray-600 hover:bg-white/80 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800/80 dark:hover:text-gray-100'
              }`}
            >
              <Sparkles className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
              Auto
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={insightsMode === 'standard'}
              id="insights-mode-standard"
              onClick={() => onInsightsModeChange('standard')}
              className={`flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all sm:min-w-[11rem] ${
                insightsMode === 'standard'
                  ? 'bg-purple-600 text-white shadow-sm ring-1 ring-purple-600/20 dark:ring-purple-400/20'
                  : 'text-gray-600 hover:bg-white/80 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800/80 dark:hover:text-gray-100'
              }`}
            >
              <ListChecks className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
              Standard
            </button>
          </div>
        </div>

        {/* Auto Data Insights Section */}
        {insightsMode === 'auto' && (
        <div className="mb-6">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div>
              <h4 className="font-medium text-gray-900 dark:text-gray-100">Auto Data Insights</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 max-w-xl">
                Run all analyses in one go. Results open in the insights sidebar when ready.
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={!canStartAuto}
            title={
              !datasetReady
                ? 'Load and select a dataset first'
                : !targetOk
                  ? 'Set a target variable in Step 1'
                  : anyRunning
                    ? 'Analysis in progress'
                    : 'Generate all insight panels'
            }
            onClick={() => {
              setDataScope(readInsightsDataScopeFromSession());
              setAutoInsightStartedByClick(true);
              void onAutoDataInsights();
            }}
            className="w-full sm:w-auto min-h-[44px] px-5 py-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 shadow-sm font-medium"
          >
            {anyRunning ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin shrink-0" />
                <span>Generating insights…</span>
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 shrink-0 opacity-90" />
                <span>Generate Auto Insights</span>
              </>
            )}
          </button>
          {!datasetReady && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">Connect a dataset in Step 1 to enable this action.</p>
          )}
          {datasetReady && !targetOk && (
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Set a target variable in Step 1 before running auto insights.</p>
          )}

          {showAutoInsightProgress && (
            <div className="mt-5 overflow-hidden rounded-xl border border-blue-200/80 dark:border-blue-800 bg-gradient-to-b from-blue-50/90 to-white dark:from-blue-950/40 dark:to-gray-900/80 shadow-sm">
              <div className="px-4 pt-4 pb-2 border-b border-blue-100 dark:border-blue-900/50">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h5 className="font-semibold text-blue-950 dark:text-blue-100 flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    Progress
                  </h5>
                  <span className="text-xs font-medium tabular-nums text-blue-800/80 dark:text-blue-300/90">
                    {anyRunning ? 'Working…' : allTerminal ? (allDoneSuccess ? 'Complete' : 'Finished with notes') : ''}{' '}
                    {!anyRunning && allTerminal && (
                      <span className="text-gray-600 dark:text-gray-400">
                        ({completedCount}/{AUTO_INSIGHT_CHECKLIST.length} ready)
                      </span>
                    )}
                  </span>
                </div>
                <div className="mt-3 h-2 w-full rounded-full bg-blue-100/80 dark:bg-blue-950/50 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-600 dark:bg-blue-500 transition-all duration-500 ease-out"
                    style={{
                      width: `${Math.max(
                        8,
                        (anyRunning
                          ? Math.min(92, (autoInsightVisibleRows / AUTO_INSIGHT_CHECKLIST.length) * 100)
                          : allTerminal
                            ? 100
                            : (completedCount / AUTO_INSIGHT_CHECKLIST.length) * 100)
                      )}%`,
                    }}
                  />
                </div>
                <p className="mt-2 text-xs text-blue-900/70 dark:text-blue-200/70">
                  Scope: <strong>{scopeDisplayLabel(dataScope)}</strong>
                  {targetOk && (
                    <>
                      {' '}
                      · Target: <strong className="font-mono text-[11px]">{targetVariable}</strong>
                    </>
                  )}
                </p>
              </div>
              <div className="px-4 py-3 flex flex-col gap-2.5">
                {AUTO_INSIGHT_CHECKLIST.slice(0, autoInsightVisibleRows).map((row, idx) => {
                  const status = autoInsightStepStatus[row.id] ?? 'idle';
                  const labelDone = status === 'done' || status === 'absent';
                  return (
                    <div
                      key={row.id}
                      className="flex items-center gap-3 min-w-0 rounded-lg bg-white/60 dark:bg-gray-800/40 px-2 py-1.5"
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100/80 dark:bg-blue-900/50 text-[11px] font-bold text-blue-800 dark:text-blue-200">
                        {idx + 1}
                      </span>
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden>
                        {status === 'running' && (
                          <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
                        )}
                        {status === 'done' && (
                          <Check className="h-4 w-4 text-green-600 dark:text-green-400" strokeWidth={2.5} />
                        )}
                        {status === 'absent' && row.id !== 'iv_analysis' && row.id !== 'variance_inflation_factor' && (
                          <span className="text-[10px] text-gray-500 dark:text-gray-400" title="No output in response">
                            —
                          </span>
                        )}
                        {status === 'absent' && (row.id === 'iv_analysis' || row.id === 'variance_inflation_factor') && (
                          <Check className="h-4 w-4 text-green-600 dark:text-green-400" strokeWidth={2.5} />
                        )}
                        {status === 'idle' && (
                          <span className="block h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600" />
                        )}
                        {status === 'error' && (
                          <span className="text-xs font-semibold text-red-600 dark:text-red-400" title="Error">
                            !
                          </span>
                        )}
                      </span>
                      <span
                        className={`text-sm truncate flex-1 ${
                          labelDone
                            ? 'text-green-800 dark:text-green-400 font-medium'
                            : status === 'error'
                              ? 'text-red-800 dark:text-red-300'
                              : 'text-blue-900 dark:text-blue-200'
                        }`}
                      >
                        {row.label}
                        {status === 'absent' && row.id !== 'iv_analysis' && row.id !== 'variance_inflation_factor' && (
                          <span className="ml-1 text-[11px] font-normal text-gray-500 dark:text-gray-400">
                            (no data in reply)
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
              {allTerminal && allDoneSuccess && (
                <div className="px-4 pb-4 text-xs text-green-800 dark:text-green-300/90 flex items-start gap-2 border-t border-green-100 dark:border-green-900/30 pt-3 mt-1">
                  <Check className="h-4 w-4 shrink-0 mt-0.5" strokeWidth={2.5} />
                  <span>
                    All analyses are ready. Open the <strong>Data Insights</strong> sidebar to explore charts and tables.
                  </span>
                </div>
              )}
              {allTerminal && errorCount > 0 && (
                <div className="px-4 pb-4 text-xs text-red-800 dark:text-red-300/90 flex items-start gap-2 border-t border-red-100 dark:border-red-900/30 pt-3 mt-1">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>
                    Something went wrong for one or more analyses. Check the chat panel for details, confirm your target
                    variable, or try <strong>Full dataset</strong> scope if splits look empty.
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
        )}

        {/* Standard Data Insights Section */}
        {insightsMode === 'standard' && (
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Standard Data Insights</h4>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">Select specific data analysis tasks to generate insights</p>

          <div className="mb-4">
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-700">
              <h5 className="font-medium text-blue-900 dark:text-blue-200 mb-2">Analysis</h5>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-blue-600"
                    checked={selectedInsightSteps.includes('bivariate_analysis')}
                    onChange={(e) => onInsightStepToggle('bivariate_analysis', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800 dark:text-blue-300">Bivariate Analysis</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-blue-600"
                    checked={selectedInsightSteps.includes('correlation_analysis')}
                    onChange={(e) => onInsightStepToggle('correlation_analysis', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800 dark:text-blue-300">Correlation analysis</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-blue-600"
                    checked={selectedInsightSteps.includes('iv_analysis')}
                    onChange={(e) => onInsightStepToggle('iv_analysis', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800 dark:text-blue-300">Information Value (IV)</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-blue-600"
                    checked={selectedInsightSteps.includes('variance_inflation_factor')}
                    onChange={(e) => onInsightStepToggle('variance_inflation_factor', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800 dark:text-blue-300">Variance Inflation Factor (VIF)</span>
                </label>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      className="rounded text-blue-600"
                      checked={selectedInsightSteps.includes('correlation_matrix')}
                      onChange={(e) => onInsightStepToggle('correlation_matrix', e.target.checked)}
                    />
                    <span className="text-sm text-blue-800 dark:text-blue-300">Correlation Matrix</span>
                  </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-blue-600"
                    checked={selectedInsightSteps.includes('correlation_ratio_analysis')}
                    onChange={(e) => onInsightStepToggle('correlation_ratio_analysis', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800 dark:text-blue-300">Correlation ratio (η)</span>
                </label>
              </div>
            </div>
          </div>
          
          <button
            type="button"
            onClick={() => void onStandardDataInsights()}
            disabled={selectedInsightSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Generate Selected Insights
          </button>
        </div>
        )}
      </div>

      {/* Chat Component */}
      {renderStepChat(3)}
    </div>
  );
};

export default Step3DataInsights;
