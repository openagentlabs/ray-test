import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Info, RefreshCw, Edit2, Calendar } from 'lucide-react';
import { fastApiService } from '../services/fastApiService';
import { parseCSV } from '../utils/csvParser';
import {
  type SplitConfiguration,
  type PartitionKey,
  createDefaultSplitConfiguration,
  buildDefaultIdentifierMapping,
} from '../utils/partitionSplitConfig';

type ColumnLike = {
  name: string;
  type: string;
  logical_type?: string;
  is_date?: boolean;
  unique_count: number;
};

interface PlatformPartitionSectionProps {
  datasetAnalysis: {
    columns: ColumnLike[];
    totalRows: number;
    totalColumns: number;
    suggestedTargetVariable?: string | null;
  } | null;
  activeDatasetId: string | null;
  selectedDataSources: any[];
  targetVariable: string;
  getDisplayType: (column: ColumnLike) => string;
  /** When true, disables all partition controls (e.g. prerequisites missing or post-confirm lock). */
  controlsDisabled?: boolean;
}

const SECTION_LABEL = 'text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide';

function readDatasetConfig(): Record<string, any> {
  try {
    const raw = sessionStorage.getItem('dataset_config');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function flushSplitToSession(merged: SplitConfiguration) {
  const cfg = readDatasetConfig();
  const sampleId =
    merged.split_method === 'user_identifier' && merged.identifier_column ? merged.identifier_column : '';
  const payload: Record<string, unknown> = {
    ...cfg,
    split_configuration: merged,
    sample_identifier_variable: sampleId,
    has_sampling_variable: false,
    sampling_variable: null,
    initial_scope: 'split',
    data_scope: 'split',
  };
  if (merged.split_method === 'user_identifier') {
    delete payload.split_ratio;
  } else if (merged.ratios) {
    payload.split_ratio = (merged.ratios.train + merged.ratios.test) / 100;
  }
  sessionStorage.setItem('dataset_config', JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent('datasetConfigChanged'));
}

function getSplitConfig(cfg: Record<string, any>): SplitConfiguration {
  const d = cfg.split_configuration;
  if (d && typeof d === 'object' && d.ingestion_mode === 'platform_split') {
    return {
      ...createDefaultSplitConfiguration(),
      ...d,
      ratios: d.ratios
        ? {
            train: Number(d.ratios.train) || 0,
            test: Number(d.ratios.test) || 0,
            validation: Number(d.ratios.validation) || 0,
          }
        : { train: 60, test: 20, validation: 20 },
    };
  }
  return createDefaultSplitConfiguration();
}

const PRESETS: { label: string; ratios: { train: number; test: number; validation: number } }[] = [
  { label: 'Standard 60/20/20', ratios: { train: 60, test: 20, validation: 20 } },
  { label: 'No validation 70/30/0', ratios: { train: 70, test: 30, validation: 0 } },
  { label: 'Conservative 50/25/25', ratios: { train: 50, test: 25, validation: 25 } },
  { label: 'Large dataset 80/10/10', ratios: { train: 80, test: 10, validation: 10 } },
];

const PARTITION_LABELS: Record<PartitionKey, string> = {
  train: 'Train partition',
  test: 'Test partition',
  validation: 'Validation partition',
};

const PILL_COLORS = [
  'bg-sky-100 text-sky-900 border-sky-200',
  'bg-emerald-100 text-emerald-900 border-emerald-200',
  'bg-amber-100 text-amber-900 border-amber-200',
  'bg-violet-100 text-violet-900 border-violet-200',
  'bg-rose-100 text-rose-900 border-rose-100',
];

function generateRandomSeed(): number {
  return Math.floor(Math.random() * 999999) + 1;
}

function formatDisplayDate(isoDate: string): string {
  if (!isoDate) return '';
  try {
    const d = new Date(isoDate);
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch {
    return isoDate;
  }
}

function formatShortDate(isoDate: string): string {
  if (!isoDate) return '';
  try {
    const d = new Date(isoDate);
    return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  } catch {
    return isoDate;
  }
}

interface TimelineVisualizationProps {
  minDate: string;
  maxDate: string;
  cutoff1: string | null;
  cutoff2: string | null;
  trainPct: number;
}

const TimelineVisualization: React.FC<TimelineVisualizationProps> = ({
  minDate,
  maxDate,
  cutoff1,
  cutoff2,
  trainPct,
}) => {
  const computeWidths = () => {
    const minTime = new Date(minDate).getTime();
    const maxTime = new Date(maxDate).getTime();
    const totalSpan = maxTime - minTime;
    if (totalSpan <= 0) return { train: 60, test: 20, holdout: 20 };

    const c1Time = cutoff1 ? new Date(cutoff1).getTime() : minTime + totalSpan * 0.6;
    const c2Time = cutoff2 ? new Date(cutoff2).getTime() : minTime + totalSpan * 0.8;

    const trainWidth = Math.max(5, Math.round(((c1Time - minTime) / totalSpan) * 100));
    const testWidth = cutoff2
      ? Math.max(5, Math.round(((c2Time - c1Time) / totalSpan) * 100))
      : Math.max(5, 100 - trainWidth);
    const holdoutWidth = cutoff2 ? Math.max(5, 100 - trainWidth - testWidth) : 0;

    return { train: trainWidth, test: testWidth, holdout: holdoutWidth };
  };

  const widths = computeWidths();

  return (
    <div className="space-y-2">
      <div className="flex h-10 rounded-lg overflow-hidden text-xs font-medium text-white">
        <div
          className="bg-green-500 flex items-center justify-center px-2"
          style={{ width: `${widths.train}%` }}
        >
          Train ({widths.train}%)
        </div>
        <div
          className="bg-yellow-500 flex items-center justify-center px-2"
          style={{ width: `${widths.test}%` }}
        >
          Test
        </div>
        {widths.holdout > 0 && (
          <div
            className="bg-amber-600 flex items-center justify-center px-2"
            style={{ width: `${widths.holdout}%` }}
          >
            Holdout
          </div>
        )}
      </div>
      <div className="flex justify-between text-xs text-gray-500">
        <span>{formatShortDate(minDate)}</span>
        {cutoff1 && <span>{formatShortDate(cutoff1)}</span>}
        {cutoff2 && <span>{formatShortDate(cutoff2)}</span>}
        <span>{formatShortDate(maxDate)}</span>
      </div>
    </div>
  );
};

const PlatformPartitionSection: React.FC<PlatformPartitionSectionProps> = ({
  datasetAnalysis,
  activeDatasetId,
  selectedDataSources,
  targetVariable,
  getDisplayType,
  controlsDisabled = false,
}) => {
  const [hasSampleIdentifier, setHasSampleIdentifier] = useState<boolean>(() => {
    const cfg = readDatasetConfig();
    const sc = getSplitConfig(cfg);
    return sc.split_method === 'user_identifier';
  });

  const [splitConfiguration, setSplitConfiguration] = useState<SplitConfiguration>(() =>
    getSplitConfig(readDatasetConfig())
  );

  const [activePreset, setActivePreset] = useState<string | 'Custom'>(() => {
    const r = getSplitConfig(readDatasetConfig()).ratios;
    if (!r) return 'Standard 60/20/20';
    const match = PRESETS.find(
      (p) => p.ratios.train === r.train && p.ratios.test === r.test && p.ratios.validation === r.validation
    );
    return match ? match.label : 'Custom';
  });

  const [valueCounts, setValueCounts] = useState<Record<string, number>>({});
  const [loadingDistribution, setLoadingDistribution] = useState(false);
  const [isEditingSeed, setIsEditingSeed] = useState(false);
  const [seedInputValue, setSeedInputValue] = useState('');
  const [ratioInputDraft, setRatioInputDraft] = useState<Partial<Record<'train' | 'test' | 'validation', string>>>({});

  // Time-based split state
  const [detectedDateRange, setDetectedDateRange] = useState<{
    min_date: string | null;
    max_date: string | null;
    cutoff_1: string | null;
    cutoff_2: string | null;
    cutoff_1_display?: string | null;  // For year-less dates (DD-Mon format)
    cutoff_2_display?: string | null;  // For year-less dates (DD-Mon format)
    has_year?: boolean;
    warning?: string;
    seasonal_warning?: string;
    total_rows?: number;
    train_rows?: number;
    test_rows?: number;
    validation_rows?: number;
  } | null>(null);
  const [loadingDateRange, setLoadingDateRange] = useState(false);
  const [totalRows, setTotalRows] = useState<number>(0);

  const dateColumns = useMemo(() => {
    if (!datasetAnalysis?.columns) return [];
    return datasetAnalysis.columns.filter((c) => getDisplayType(c) === 'Date').map((c) => c.name);
  }, [datasetAnalysis, getDisplayType]);

  const identifierColumnCandidates = useMemo(() => {
    if (!datasetAnalysis?.columns) return [];
    const tv = targetVariable?.trim();
    return datasetAnalysis.columns.filter((c) => {
      if (tv && c.name === tv) return false;
      if (getDisplayType(c) === 'Numerical') return false;
      const uniqueCount = c.unique_count ?? 999;
      if (uniqueCount < 2 || uniqueCount > 5) return false;
      return true;
    });
  }, [datasetAnalysis, targetVariable, getDisplayType]);

  const persist = useCallback((updates: Partial<SplitConfiguration>) => {
    setSplitConfiguration((prev) => {
      const merged: SplitConfiguration = { ...prev, ...updates };
      flushSplitToSession(merged);
      return merged;
    });
  }, []);

  useEffect(() => {
    const cfg = readDatasetConfig();
    const sc = getSplitConfig(cfg);
    setSplitConfiguration(sc);
    setHasSampleIdentifier(sc.split_method === 'user_identifier');
  }, [datasetAnalysis?.totalRows, targetVariable]);

  useEffect(() => {
    if (!datasetAnalysis) return;
    const cfg = readDatasetConfig();
    if (cfg.split_configuration && typeof cfg.split_configuration === 'object') return;
    const sc = createDefaultSplitConfiguration();
    sc.seed = generateRandomSeed();
    const next = {
      ...cfg,
      split_configuration: sc,
      split_ratio: (sc.ratios!.train + sc.ratios!.test) / 100,
      initial_scope: 'split',
      data_scope: 'split',
      has_sampling_variable: false,
      sampling_variable: null,
    };
    sessionStorage.setItem('dataset_config', JSON.stringify(next));
    setSplitConfiguration(sc);
  }, [datasetAnalysis]);

  useEffect(() => {
    if (
      splitConfiguration.split_method === 'stratified_random' &&
      (splitConfiguration.seed === null || splitConfiguration.seed === undefined)
    ) {
      persist({ seed: generateRandomSeed() });
    }
  }, [splitConfiguration.split_method, splitConfiguration.seed, persist]);

  const loadDistributionForColumn = useCallback(
    async (columnName: string) => {
      if (!columnName) {
        setValueCounts({});
        return;
      }
      setLoadingDistribution(true);
      try {
        if (activeDatasetId) {
          const res = await fastApiService.getColumnDistribution(activeDatasetId, columnName, 10, true);
          if (res.success && res.distribution) {
            setValueCounts(res.distribution as Record<string, number>);
            return;
          }
        }
        const fileSource = selectedDataSources.find((s) => s?.type === 'file' && s?.file instanceof File);
        const file = fileSource?.file as File | undefined;
        if (file) {
          const text = await file.text();
          const parsed = parseCSV(text);
          const counts: Record<string, number> = {};
          for (const row of parsed.data) {
            const v = row[columnName];
            const key = v === null || v === undefined || v === '' ? '__NULL__' : String(v);
            counts[key] = (counts[key] || 0) + 1;
          }
          setValueCounts(counts);
          return;
        }
        setValueCounts({});
      } catch {
        setValueCounts({});
      } finally {
        setLoadingDistribution(false);
      }
    },
    [activeDatasetId, selectedDataSources]
  );

  useEffect(() => {
    if (splitConfiguration.split_method !== 'user_identifier' || !splitConfiguration.identifier_column) {
      setValueCounts({});
      return;
    }
    loadDistributionForColumn(splitConfiguration.identifier_column);
  }, [splitConfiguration.split_method, splitConfiguration.identifier_column, loadDistributionForColumn]);

  // Fetch computed cutoffs when time-based split is selected or ratios change
  useEffect(() => {
    if (splitConfiguration.split_method !== 'time_based' || !splitConfiguration.date_column) {
      setDetectedDateRange(null);
      return;
    }

    // Try to find the file from selectedDataSources
    const fileSource = selectedDataSources.find((s) => s?.type === 'file' && s?.file instanceof File);
    const file = fileSource?.file as File | undefined;
    
    if (!file) {
      console.log('[PlatformPartitionSection] No file found in selectedDataSources:', selectedDataSources);
      return;
    }

    let cancelled = false;

    const fetchDateRange = async () => {
      setLoadingDateRange(true);
      try {
        // Get exclusion rules from sessionStorage
        let exclusionRules: Array<{
          id: string;
          conditions: Array<{
            column: string;
            operator: string;
            value: string | number | string[] | [number, number] | null;
            connector: 'AND' | 'OR';
          }>;
        }> | undefined;
        try {
          const cfgRaw = sessionStorage.getItem('dataset_config');
          const cfg = cfgRaw ? JSON.parse(cfgRaw) : {};
          exclusionRules = cfg.exclusion_rules;
        } catch {
          // Ignore parse errors
        }

        console.log('[PlatformPartitionSection] Fetching date range for:', splitConfiguration.date_column, 'with ratios:', splitConfiguration.ratios);
        const response = await fastApiService.partitionPreview({
          file,
          split_configuration: {
            ingestion_mode: 'platform_split',
            split_method: 'time_based',
            date_column: splitConfiguration.date_column,
            ratios: splitConfiguration.ratios || { train: 60, test: 20, validation: 20 },
            cutoff_1: splitConfiguration.cutoff_1 || undefined,
            cutoff_2: splitConfiguration.cutoff_2 || undefined,
          },
          target_variable: targetVariable || '_placeholder_',
          exclusion_rules: exclusionRules,
        });
        console.log('[PlatformPartitionSection] Partition preview response:', response);
        if (!cancelled && response.success && response.computed_cutoffs) {
          setDetectedDateRange(response.computed_cutoffs);
          setTotalRows(response.total_rows || 0);
        } else if (!cancelled && response.success && !response.computed_cutoffs) {
          console.warn('[PlatformPartitionSection] Response success but no computed_cutoffs');
        }
      } catch (err) {
        if (!cancelled) {
          console.error('[PlatformPartitionSection] Failed to fetch date range:', err);
        }
      } finally {
        if (!cancelled) {
          setLoadingDateRange(false);
        }
      }
    };

    const debounce = setTimeout(fetchDateRange, 300);
    return () => {
      cancelled = true;
      clearTimeout(debounce);
    };
  }, [
    splitConfiguration.split_method,
    splitConfiguration.date_column,
    splitConfiguration.ratios?.train,
    splitConfiguration.ratios?.test,
    splitConfiguration.ratios?.validation,
    splitConfiguration.cutoff_1,
    splitConfiguration.cutoff_2,
    selectedDataSources,
    targetVariable,
  ]);

  const uniqueValuesSorted = useMemo(() => {
    return Object.keys(valueCounts).sort((a, b) => a.localeCompare(b));
  }, [valueCounts]);

  const nullCount = valueCounts['__NULL__'] ?? 0;

  const identifierMapping = splitConfiguration.identifier_mapping || {};

  const setMapping = (partition: 'train' | 'test', rawValue: string) => {
    setSplitConfiguration((prev) => {
      const next = { ...(prev.identifier_mapping || {}) };
      if (!rawValue) delete next[partition];
      else next[partition] = rawValue;
      const merged = { ...prev, identifier_mapping: next };
      flushSplitToSession(merged);
      return merged;
    });
  };

  const setValidationMapping = (values: string[]) => {
    setSplitConfiguration((prev) => {
      const next = { ...(prev.identifier_mapping || {}) };
      if (values.length === 0) {
        delete next.validation;
      } else {
        next.validation = values.slice(0, 3);
      }
      const merged = { ...prev, identifier_mapping: next };
      flushSplitToSession(merged);
      return merged;
    });
  };

  const availableForValidation = useMemo(() => {
    const allValues = uniqueValuesSorted.filter((v) => v !== '__NULL__');
    const trainVal = identifierMapping.train;
    const testVal = identifierMapping.test;
    return allValues.filter((v) => v !== trainVal && v !== testVal);
  }, [uniqueValuesSorted, identifierMapping.train, identifierMapping.test]);

  const validationValues = useMemo(() => {
    const val = identifierMapping.validation;
    if (Array.isArray(val)) return val;
    if (typeof val === 'string' && val) return [val];
    return [];
  }, [identifierMapping.validation]);

  const onSelectIdentifierColumn = (col: string) => {
    if (!col) {
      setValueCounts({});
      persist({ identifier_column: null, identifier_mapping: {} });
      return;
    }
    persist({ identifier_column: col, identifier_mapping: {} });
    loadDistributionForColumn(col);
  };

  useEffect(() => {
    if (splitConfiguration.split_method !== 'user_identifier' || !splitConfiguration.identifier_column) return;
    if (uniqueValuesSorted.length === 0) return;
    const current = splitConfiguration.identifier_mapping || {};
    const hasAny = Object.keys(current).length > 0;
    if (hasAny) return;
    const auto = buildDefaultIdentifierMapping(uniqueValuesSorted.filter((v) => v !== '__NULL__'));
    setSplitConfiguration((prev) => {
      const merged = { ...prev, identifier_mapping: auto };
      flushSplitToSession(merged);
      return merged;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only backfill when values first arrive
  }, [uniqueValuesSorted.join('|')]);

  useEffect(() => {
    if (splitConfiguration.split_method !== 'user_identifier') return;
    if (!splitConfiguration.identifier_column) return;
    
    const trainVal = identifierMapping.train;
    const testVal = identifierMapping.test;
    
    if (!trainVal || !testVal) return;
    
    const currentValidation = identifierMapping.validation;
    const hasValidation = Array.isArray(currentValidation) ? currentValidation.length > 0 : !!currentValidation;
    if (hasValidation) return;
    
    const allValues = uniqueValuesSorted.filter((v) => v !== '__NULL__');
    const remaining = allValues.filter((v) => v !== trainVal && v !== testVal);
    
    if (remaining.length > 0) {
      setValidationMapping(remaining.slice(0, 3));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identifierMapping.train, identifierMapping.test, splitConfiguration.split_method, splitConfiguration.identifier_column]);

  const sumRatios =
    (splitConfiguration.ratios?.train ?? 0) +
    (splitConfiguration.ratios?.test ?? 0) +
    (splitConfiguration.ratios?.validation ?? 0);

  const applyPreset = (label: string) => {
    const p = PRESETS.find((x) => x.label === label);
    if (!p) return;
    setActivePreset(label);
    setRatioInputDraft({});
    persist({ ratios: { ...p.ratios } });
  };

  const showTimeBasedOption = dateColumns.length > 0;

  if (!datasetAnalysis) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 text-sm text-gray-500 dark:text-gray-400">
        Upload and analyze a dataset to configure partitioning.
      </div>
    );
  }

  return (
    <fieldset
      disabled={controlsDisabled}
      className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-8 min-w-0 ${
        controlsDisabled ? 'opacity-60' : ''
      }`}
    >
      <div>
        <p className={SECTION_LABEL}>Does your dataset already have a sample identifier?</p>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-4xl">
          A sample identifier is a column in your dataset that already marks which partition each row belongs to (e.g.
          values like <code className="text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-300 px-1 rounded">train</code>,{' '}
          <code className="text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-300 px-1 rounded">test</code>,{' '}
          <code className="text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-300 px-1 rounded">validation</code>). If selected, the platform will use this
          column to partition the data instead of splitting it.
        </p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => {
              setHasSampleIdentifier(false);
              persist({
                split_method: 'stratified_random',
                identifier_column: null,
                identifier_mapping: {},
                ratios: splitConfiguration.ratios ?? { train: 60, test: 20, validation: 20 },
                date_column: null,
              });
              setActivePreset(
                PRESETS.find(
                  (p) =>
                    p.ratios.train === (splitConfiguration.ratios?.train ?? 60) &&
                    p.ratios.test === (splitConfiguration.ratios?.test ?? 20) &&
                    p.ratios.validation === (splitConfiguration.ratios?.validation ?? 20)
                )?.label ?? 'Custom'
              );
            }}
            className={`text-left rounded-xl border-2 p-5 transition-shadow ${
              !hasSampleIdentifier ? 'border-blue-600 ring-2 ring-blue-100 dark:ring-blue-900/50 shadow-sm' : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <div className="flex justify-between items-start gap-2">
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">No - Platform will split</p>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  I don&apos;t have a sample identifier. The platform should partition my data based on the method I
                  choose below.
                </p>
              </div>
              <span
                className={`mt-1 h-5 w-5 rounded-full border-2 flex-shrink-0 ${
                  !hasSampleIdentifier ? 'border-blue-600 bg-blue-600' : 'border-gray-300 dark:border-gray-500'
                }`}
                aria-hidden
              />
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              setHasSampleIdentifier(true);
              persist({
                split_method: 'user_identifier',
                ratios: null,
                seed: null,
                date_column: null,
              });
            }}
            className={`text-left rounded-xl border-2 p-5 transition-shadow ${
              hasSampleIdentifier ? 'border-blue-600 ring-2 ring-blue-100 dark:ring-blue-900/50 shadow-sm' : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <div className="flex justify-between items-start gap-2">
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">Yes - I have a sample identifier</p>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  My dataset has a column that already defines the train / test / validation assignment for each row.
                </p>
              </div>
              <span
                className={`mt-1 h-5 w-5 rounded-full border-2 flex-shrink-0 ${
                  hasSampleIdentifier ? 'border-blue-600 bg-blue-600' : 'border-gray-300 dark:border-gray-500'
                }`}
                aria-hidden
              />
            </div>
          </button>
        </div>
      </div>

      {!hasSampleIdentifier && (
        <div className="space-y-4">
          <div>
            <p className={SECTION_LABEL}>How should we partition your data?</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 uppercase tracking-wide">Shown when no sample identifier</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => persist({ split_method: 'stratified_random' })}
              className={`text-left rounded-xl border-2 p-5 transition-shadow ${
                splitConfiguration.split_method === 'stratified_random'
                  ? 'border-blue-600 ring-2 ring-blue-100 dark:ring-blue-900/50'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
              }`}
            >
              <div className="flex justify-between items-start gap-2">
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">Stratified random split</p>
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    Randomly assigns rows to partitions while preserving the target variable distribution in each.
                  </p>
                </div>
                <span
                  className={`mt-1 h-5 w-5 rounded-full border-2 flex-shrink-0 ${
                    splitConfiguration.split_method === 'stratified_random'
                      ? 'border-blue-600 bg-blue-600'
                      : 'border-gray-300 dark:border-gray-500'
                  }`}
                />
              </div>
            </button>

            {showTimeBasedOption ? (
              <button
                type="button"
                onClick={() =>
                  persist({
                    split_method: 'time_based',
                    date_column: splitConfiguration.date_column || dateColumns[0] || null,
                  })
                }
                className={`text-left rounded-xl border-2 p-5 transition-shadow ${
                  splitConfiguration.split_method === 'time_based'
                    ? 'border-blue-600 ring-2 ring-blue-100 dark:ring-blue-900/50'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                }`}
              >
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <p className="font-semibold text-gray-900 dark:text-white inline-flex items-center gap-2 flex-wrap">
                      Time-based split
                      <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/40 px-2 py-0.5 rounded-full">
                        Recommended
                      </span>
                    </p>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                      Sorts chronologically. Earlier records train, recent records evaluate. More realistic for production.
                    </p>
                  </div>
                  <span
                    className={`mt-1 h-5 w-5 rounded-full border-2 flex-shrink-0 ${
                      splitConfiguration.split_method === 'time_based' ? 'border-blue-600 bg-blue-600' : 'border-gray-300 dark:border-gray-500'
                    }`}
                  />
                </div>
              </button>
            ) : null}
          </div>

          {showTimeBasedOption && (
            <div className="flex items-start gap-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 px-4 py-3 text-sm text-blue-900 dark:text-blue-100">
              <Info className="h-5 w-5 flex-shrink-0 text-blue-600 dark:text-blue-400 mt-0.5" />
              <p>
                Date columns detected:{' '}
                {dateColumns.map((name) => (
                  <code key={name} className="mx-0.5 text-xs bg-white/80 dark:bg-gray-700 dark:text-blue-200 px-1.5 py-0.5 rounded border border-blue-100 dark:border-blue-700">
                    {name}
                  </code>
                ))}
                . Time-based split recommended for more realistic evaluation.
              </p>
            </div>
          )}

          {splitConfiguration.split_method === 'time_based' && dateColumns.length > 0 && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-5">
              <div className="flex items-center gap-3">
                <p className={SECTION_LABEL}>Time-based split configuration</p>
                <span className="text-xs font-medium text-emerald-600 uppercase tracking-wide">
                  Only if time-based selected
                </span>
              </div>

              {/* Date column and detected range row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date column</label>
                  <select
                    value={splitConfiguration.date_column || dateColumns[0] || ''}
                    onChange={(e) => {
                      persist({ date_column: e.target.value || null, cutoff_1: null, cutoff_2: null });
                      setDetectedDateRange(null);
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {dateColumns.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Detected range</label>
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 font-medium">
                    {loadingDateRange ? (
                      <span className="text-gray-500 dark:text-gray-400">Loading...</span>
                    ) : detectedDateRange?.min_date && detectedDateRange?.max_date ? (
                      <>
                        {detectedDateRange.has_year === false 
                          ? `${detectedDateRange.min_date} - ${detectedDateRange.max_date}`
                          : `${formatDisplayDate(detectedDateRange.min_date)} - ${formatDisplayDate(detectedDateRange.max_date)}`
                        }
                        <span className="text-gray-500 dark:text-gray-400 font-normal ml-2">({totalRows.toLocaleString()} rows)</span>
                      </>
                    ) : (
                      <span className="text-gray-500 dark:text-gray-400">No date range detected</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Warning for year-less date columns */}
              {detectedDateRange?.has_year === false && detectedDateRange?.warning && (
                <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
                  <svg className="w-5 h-5 text-amber-500 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-sm text-amber-800 dark:text-amber-200">{detectedDateRange.warning}</p>
                </div>
              )}

              {/* Seasonal warning - partition covers less than 3 months */}
              {detectedDateRange?.seasonal_warning && (
                <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
                  <svg className="w-5 h-5 text-amber-500 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-sm text-amber-800 dark:text-amber-200">{detectedDateRange.seasonal_warning}</p>
                </div>
              )}

              {/* Cutoff dates section */}
              <div className="border-t border-gray-100 dark:border-gray-700 pt-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Cutoff dates</p>
                    <span className="text-xs text-gray-500 dark:text-gray-400">- Auto-computed from ratios. Override with manual values.</span>
                  </div>
                  {loadingDateRange && (
                    <span className="flex items-center gap-1.5 text-xs text-blue-600">
                      <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Recalculating...
                    </span>
                  )}
                </div>

                {/* For year-less dates: show text inputs with dynamic placeholder based on data format */}
                {detectedDateRange?.has_year === false ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Cutoff 1 - Train / Test boundary
                        </label>
                        <div className="flex gap-2">
                          <div className="flex-1 px-3 py-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg text-blue-900 dark:text-blue-100 font-medium">
                            <span className="text-xs text-blue-600 dark:text-blue-400 mr-2">Auto:</span>
                            {detectedDateRange?.cutoff_1_display || 'Not computed'}
                          </div>
                          <input
                            type="text"
                            placeholder={detectedDateRange?.min_date ? `e.g., ${detectedDateRange.min_date}` : 'e.g., 15-Aug'}
                            value={splitConfiguration.cutoff_1 || ''}
                            onChange={(e) => persist({ cutoff_1: e.target.value || null })}
                            className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                          />
                        </div>
                      </div>

                      {(splitConfiguration.ratios?.validation ?? 0) > 0 && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Cutoff 2 - Test / Validation boundary
                          </label>
                          <div className="flex gap-2">
                            <div className="flex-1 px-3 py-2 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg text-green-900 dark:text-green-100 font-medium">
                              <span className="text-xs text-green-600 dark:text-green-400 mr-2">Auto:</span>
                              {detectedDateRange?.cutoff_2_display || 'Not computed'}
                            </div>
                            <input
                              type="text"
                              placeholder={detectedDateRange?.max_date ? `e.g., ${detectedDateRange.max_date}` : 'e.g., 20-Oct'}
                              value={splitConfiguration.cutoff_2 || ''}
                              onChange={(e) => persist({ cutoff_2: e.target.value || null })}
                              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                      Enter manual cutoff date to override auto-computed values.
                    </p>
                  </div>
                ) : (
                  /* For dates with year: show editable date pickers */
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Cutoff 1 - Train / Test boundary
                      </label>
                      <div className="relative">
                        <input
                          type="date"
                          value={splitConfiguration.cutoff_1 || detectedDateRange?.cutoff_1 || ''}
                          onChange={(e) => persist({ cutoff_1: e.target.value || null })}
                          min={detectedDateRange?.min_date || undefined}
                          max={detectedDateRange?.max_date || undefined}
                          className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                      </div>
                    </div>

                    {(splitConfiguration.ratios?.validation ?? 0) > 0 && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Cutoff 2 - Test / Validation boundary
                        </label>
                        <div className="relative">
                          <input
                            type="date"
                            value={splitConfiguration.cutoff_2 || detectedDateRange?.cutoff_2 || ''}
                            onChange={(e) => persist({ cutoff_2: e.target.value || null })}
                            min={splitConfiguration.cutoff_1 || detectedDateRange?.cutoff_1 || detectedDateRange?.min_date || undefined}
                            max={detectedDateRange?.max_date || undefined}
                            className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Timeline visualization for year-less dates - uses actual row counts from backend */}
              {detectedDateRange?.has_year === false && detectedDateRange?.min_date && detectedDateRange?.max_date && (
                <div className="border-t border-gray-100 dark:border-gray-700 pt-5">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Timeline Visualization</p>
                    {loadingDateRange && (
                      <span className="flex items-center gap-1.5 text-xs text-blue-600">
                        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Updating preview...
                      </span>
                    )}
                  </div>
                  <div className={`space-y-2 transition-opacity ${loadingDateRange ? 'opacity-50' : 'opacity-100'}`}>
                    {(() => {
                      const totalRows = detectedDateRange.total_rows || 1;
                      const trainPct = detectedDateRange.train_rows ? (detectedDateRange.train_rows / totalRows) * 100 : (splitConfiguration.ratios?.train ?? 60);
                      const testPct = detectedDateRange.test_rows ? (detectedDateRange.test_rows / totalRows) * 100 : (splitConfiguration.ratios?.test ?? 20);
                      const valPct = detectedDateRange.validation_rows ? (detectedDateRange.validation_rows / totalRows) * 100 : (splitConfiguration.ratios?.validation ?? 0);
                      
                      return (
                        <>
                          <div className="flex h-8 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-600">
                            <div 
                              className="bg-blue-500 flex items-center justify-center text-white text-xs font-medium"
                              style={{ width: `${trainPct}%` }}
                            >
                              Train ({detectedDateRange.train_rows ?? '-'})
                            </div>
                            <div 
                              className="bg-green-500 flex items-center justify-center text-white text-xs font-medium"
                              style={{ width: `${testPct}%` }}
                            >
                              Test ({detectedDateRange.test_rows ?? '-'})
                            </div>
                            {valPct > 0 && (
                              <div 
                                className="bg-purple-500 flex items-center justify-center text-white text-xs font-medium"
                                style={{ width: `${valPct}%` }}
                              >
                                Validation ({detectedDateRange.validation_rows ?? '-'})
                              </div>
                            )}
                          </div>
                          <div className="flex justify-between text-xs text-gray-500">
                            <span>{detectedDateRange.min_date}</span>
                            {detectedDateRange.cutoff_1_display && (
                              <span className="text-blue-600 font-medium">↓ {detectedDateRange.cutoff_1_display}</span>
                            )}
                            {detectedDateRange.cutoff_2_display && valPct > 0 && (
                              <span className="text-green-600 font-medium">↓ {detectedDateRange.cutoff_2_display}</span>
                            )}
                            <span>{detectedDateRange.max_date}</span>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>
              )}

              {/* Timeline visualization for dates with year */}
              {detectedDateRange?.has_year !== false && detectedDateRange?.min_date && detectedDateRange?.max_date && (
                <div className="border-t border-gray-100 dark:border-gray-700 pt-5">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Timeline Visualization</p>
                    {loadingDateRange && (
                      <span className="flex items-center gap-1.5 text-xs text-blue-600">
                        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Updating preview...
                      </span>
                    )}
                  </div>
                  <div className={`transition-opacity ${loadingDateRange ? 'opacity-50' : 'opacity-100'}`}>
                    <TimelineVisualization
                      minDate={detectedDateRange.min_date}
                      maxDate={detectedDateRange.max_date}
                      cutoff1={splitConfiguration.cutoff_1 || detectedDateRange.cutoff_1}
                      cutoff2={(splitConfiguration.ratios?.validation ?? 0) > 0 ? (splitConfiguration.cutoff_2 || detectedDateRange.cutoff_2) : null}
                      trainPct={splitConfiguration.ratios?.train ?? 60}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-4">
            <p className={SECTION_LABEL}>Partition ratios</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => applyPreset(p.label)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                    activePreset === p.label
                      ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-gray-900 dark:border-gray-100'
                      : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                  }`}
                >
                  {p.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setActivePreset('Custom');
                  setRatioInputDraft({});
                }}
                className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                  activePreset === 'Custom'
                    ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-gray-900 dark:border-gray-100'
                    : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                }`}
              >
                Custom
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {(['train', 'test', 'validation'] as const).map((key) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 capitalize">
                    {key}
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="off"
                      value={
                        ratioInputDraft[key] !== undefined
                          ? ratioInputDraft[key]!
                          : String(splitConfiguration.ratios?.[key] ?? 0)
                      }
                      onChange={(e) => {
                        const digits = e.target.value.replace(/\D/g, '').slice(0, 3);
                        setRatioInputDraft((prev) => ({ ...prev, [key]: digits }));
                        if (digits === '') return;
                        const n = parseInt(digits, 10);
                        if (Number.isNaN(n)) return;
                        const clamped = Math.max(0, Math.min(100, n));
                        const r = {
                          ...(splitConfiguration.ratios || { train: 0, test: 0, validation: 0 }),
                          [key]: clamped,
                        };
                        setActivePreset('Custom');
                        persist({ ratios: r });
                      }}
                      onBlur={(e) => {
                        const digits = e.target.value.replace(/\D/g, '');
                        const n = digits === '' ? 0 : Math.max(0, Math.min(100, parseInt(digits, 10) || 0));
                        const r = {
                          ...(splitConfiguration.ratios || { train: 0, test: 0, validation: 0 }),
                          [key]: n,
                        };
                        setActivePreset('Custom');
                        persist({ ratios: r });
                        setRatioInputDraft((prev) => {
                          const next = { ...prev };
                          delete next[key];
                          return next;
                        });
                      }}
                      className="w-full px-3 py-2 pr-8 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400 text-sm pointer-events-none">
                      %
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-medium ${
                  sumRatios === 100 ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300'
                }`}
              >
                {sumRatios === 100 ? '✓ Sum: 100%' : `Sum: ${sumRatios}%`}
              </span>
              <span className="text-gray-500 dark:text-gray-400">Integers only. Must total exactly 100%.</span>
            </div>

            {sumRatios !== 100 && (
              <p className="text-sm text-amber-800 dark:text-amber-200" role="status">
                The sum of partition ratios must equal 100%. Current total: {sumRatios}%.
              </p>
            )}

            {splitConfiguration.ratios && (
              <div className="flex h-10 rounded-lg overflow-hidden text-xs font-medium text-white">
                {splitConfiguration.ratios.train > 0 && (
                  <div
                    className="bg-sky-600 flex items-center justify-center px-1"
                    style={{ width: `${splitConfiguration.ratios.train}%` }}
                  >
                    Train {splitConfiguration.ratios.train}%
                  </div>
                )}
                {splitConfiguration.ratios.test > 0 && (
                  <div
                    className="bg-emerald-600 flex items-center justify-center px-1"
                    style={{ width: `${splitConfiguration.ratios.test}%` }}
                  >
                    Test {splitConfiguration.ratios.test}%
                  </div>
                )}
                {splitConfiguration.ratios.validation > 0 && (
                  <div
                    className="bg-amber-500 flex items-center justify-center px-1"
                    style={{ width: `${splitConfiguration.ratios.validation}%` }}
                  >
                    Valid {splitConfiguration.ratios.validation}%
                  </div>
                )}
              </div>
            )}
          </div>

          {splitConfiguration.split_method === 'stratified_random' && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-3">
              <div className="flex items-center gap-3">
                <p className={SECTION_LABEL}>Seed configuration</p>
                <span className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wide">
                  Only for stratified random
                </span>
              </div>

              <div className="flex items-center gap-4">
                <label className="text-sm text-gray-700 dark:text-gray-300">Random seed:</label>
                {isEditingSeed ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={999999}
                      value={seedInputValue}
                      onChange={(e) => setSeedInputValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          const n = parseInt(seedInputValue, 10);
                          if (!Number.isNaN(n) && n >= 1 && n <= 999999) {
                            persist({ seed: n });
                          }
                          setIsEditingSeed(false);
                        } else if (e.key === 'Escape') {
                          setIsEditingSeed(false);
                        }
                      }}
                      className="w-28 px-3 py-1.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const n = parseInt(seedInputValue, 10);
                        if (!Number.isNaN(n) && n >= 1 && n <= 999999) {
                          persist({ seed: n });
                        }
                        setIsEditingSeed(false);
                      }}
                      className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsEditingSeed(false)}
                      className="px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="inline-flex items-center px-4 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-lg text-sm font-mono font-medium text-gray-900 dark:text-gray-100 min-w-[90px] justify-center">
                      {splitConfiguration.seed ?? '-'}
                    </span>
                    <button
                      type="button"
                      onClick={() => persist({ seed: generateRandomSeed() })}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <RefreshCw className="h-4 w-4" />
                      Regenerate
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSeedInputValue(String(splitConfiguration.seed ?? ''));
                        setIsEditingSeed(true);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <Edit2 className="h-4 w-4" />
                      Edit
                    </button>
                  </>
                )}
              </div>

              <p className="text-xs text-gray-500 dark:text-gray-400">
                Auto-generated (1-999999). Stored in project metadata for reproducibility. &quot;Regenerate&quot; creates
                a new seed + re-executes the split preview.
              </p>
            </div>
          )}
        </div>
      )}

      {hasSampleIdentifier && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-5">
          <p className={SECTION_LABEL}>Sample identifier configuration</p>

          <div className="flex flex-col lg:flex-row lg:items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Select the identifier column</label>
              <select
                value={splitConfiguration.identifier_column || ''}
                onChange={(e) => onSelectIdentifierColumn(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select column…</option>
                {identifierColumnCandidates.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({getDisplayType(c)}, {c.unique_count} uniques)
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Detected unique values</p>
              {loadingDistribution ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {uniqueValuesSorted
                    .filter((v) => v !== '__NULL__')
                    .map((v, i) => (
                      <span
                        key={v}
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${PILL_COLORS[i % PILL_COLORS.length]}`}
                      >
                        {v} ({(valueCounts[v] ?? 0).toLocaleString()})
                      </span>
                    ))}
                  {uniqueValuesSorted.filter((v) => v !== '__NULL__').length === 0 && splitConfiguration.identifier_column && (
                    <span className="text-sm text-gray-500 dark:text-gray-400">No values yet</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {nullCount > 0 && (
            <div className="rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
              {nullCount.toLocaleString()} rows have null values in the identifier column. These rows will be excluded from
              all partitions.
            </div>
          )}

          {uniqueValuesSorted.filter((v) => v !== '__NULL__').length > 5 && (
            <div className="rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
              More than 5 unique values detected. Sample identifier columns should have 2-5 unique values. Please check if this is the correct column.
            </div>
          )}

          <div className="border-t border-gray-100 dark:border-gray-700 pt-4 space-y-3">
            <p className={SECTION_LABEL}>Map values to partitions</p>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Select values for Train and Test. Remaining values will be auto-selected for Validation (up to 3). Review before proceeding.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Train partition - single select */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{PARTITION_LABELS.train}</label>
                <select
                  value={identifierMapping.train ?? ''}
                  onChange={(e) => setMapping('train', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">- Select -</option>
                  {uniqueValuesSorted
                    .filter((v) => v !== '__NULL__' && v !== identifierMapping.test)
                    .map((v) => (
                      <option key={v} value={v}>
                        {v} ({(valueCounts[v] ?? 0).toLocaleString()} rows)
                      </option>
                    ))}
                </select>
              </div>

              {/* Test partition - single select */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{PARTITION_LABELS.test}</label>
                <select
                  value={identifierMapping.test ?? ''}
                  onChange={(e) => setMapping('test', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">- Select -</option>
                  {uniqueValuesSorted
                    .filter((v) => v !== '__NULL__' && v !== identifierMapping.train)
                    .map((v) => (
                      <option key={v} value={v}>
                        {v} ({(valueCounts[v] ?? 0).toLocaleString()} rows)
                      </option>
                    ))}
                </select>
              </div>

              {/* Validation partition - multi-select checkbox list */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {PARTITION_LABELS.validation}
                  <span className="text-xs text-gray-500 dark:text-gray-400 font-normal ml-1">(up to 3)</span>
                </label>
                {availableForValidation.length === 0 ? (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-500 dark:text-gray-400">
                    Select Train and Test first
                  </div>
                ) : (
                  <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2 bg-white dark:bg-gray-800 max-h-40 overflow-y-auto">
                    {availableForValidation.map((v) => {
                      const isSelected = validationValues.includes(v);
                      const canSelect = isSelected || validationValues.length < 3;
                      return (
                        <label
                          key={v}
                          className={`flex items-center gap-2 cursor-pointer ${!canSelect ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={!canSelect}
                            onChange={() => {
                              if (isSelected) {
                                setValidationMapping(validationValues.filter((x) => x !== v));
                              } else if (validationValues.length < 3) {
                                setValidationMapping([...validationValues, v]);
                              }
                            }}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-900 dark:text-gray-100">
                            {v} <span className="text-gray-500 dark:text-gray-400">({(valueCounts[v] ?? 0).toLocaleString()} rows)</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
                {validationValues.length > 0 && (
                  <p className="text-xs text-blue-600 mt-1">
                    {validationValues.length} value{validationValues.length > 1 ? 's' : ''} selected. Review before proceeding.
                  </p>
                )}
              </div>
            </div>
          </div>

          {uniqueValuesSorted.filter((v) => v !== '__NULL__').length === 2 && (
            <p className="text-sm text-blue-800 dark:text-blue-200 bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded-lg px-3 py-2">
              Only two partition values detected. Validation will be empty - only Train and Test partitions available.
            </p>
          )}

          <div className="flex items-start gap-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 px-4 py-3 text-sm text-blue-900 dark:text-blue-100">
            <Info className="h-5 w-5 flex-shrink-0 text-blue-600 dark:text-blue-400 mt-0.5" />
            <p>
              When a sample identifier is used, the platform skips ratio configuration and seed/date cutoff settings. It
              proceeds directly to partition statistics review in the next steps.
            </p>
          </div>
        </div>
      )}
    </fieldset>
  );
};

/** Validate split config for submit; returns error message or null. */
export function validateSplitConfigurationForSubmit(
  hasSampleId: boolean,
  sc: SplitConfiguration,
  targetVariable: string
): string | null {
  if (hasSampleId || sc.split_method === 'user_identifier') {
    if (!sc.identifier_column?.trim()) return 'Please select a sample identifier column.';
    const m = sc.identifier_mapping || {};
    if (!m.train?.trim()) return 'A training partition is required.';
    
    const vals: string[] = [];
    if (m.train) vals.push(m.train);
    if (m.test) vals.push(m.test);
    if (Array.isArray(m.validation)) {
      vals.push(...m.validation);
    } else if (typeof m.validation === 'string' && m.validation) {
      vals.push(m.validation);
    }
    
    if (new Set(vals).size !== vals.length) return 'Each column value can map to at most one partition.';
    return null;
  }
  if (sc.split_method === 'time_based' && !sc.date_column?.trim()) return 'Please select a date column for time-based split.';
  const r = sc.ratios;
  if (!r) return 'Partition ratios are required.';
  if (r.train + r.test + r.validation !== 100) return 'Train, test, and validation percentages must sum to 100%.';
  if (!targetVariable?.trim()) return 'Select a target variable before partitioning.';
  return null;
}

export default PlatformPartitionSection;
