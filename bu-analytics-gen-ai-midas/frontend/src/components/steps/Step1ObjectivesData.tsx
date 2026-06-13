import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import {
  Plus,
  Eye,
  EyeOff,
  CheckCircle,
  Check,
  X,
  Upload,
  FileText,
  ArrowRight,
  ChevronDown,
  Settings,
  AlertCircle,
  Bot,
  Loader2,
} from 'lucide-react';
import { INTEGRATION_DATA_SOURCES, IntegrationDataSource, getConnectionStrategy } from '../DataSourceSelection';
import { formatFileSize } from '../../utils/csvParser';
import UserKnowledgeUploadPanel from '../UserKnowledgeUploadPanel';
import PlatformPartitionSection from '../PlatformPartitionSection';
import ReviewStatsPanel from '../ReviewStatsPanel';
import ExclusionRulesPanel from '../ExclusionRulesPanel';
import VariableReviewPanel from '../VariableReviewPanel';
import { fastApiService } from '../../services/fastApiService';
import { useDocumentation } from '../../contexts/DocumentationContext';
import { ExclusionGroup } from './types';

/** Mirrors ModelBuilder: lets submit use existing_dataset_id without child state */
const STAGED_CHUNKED_DATASET_ID_KEY = 'staged_chunked_dataset_id';
const STAGED_CHUNKED_FILE_META_KEY = 'staged_chunked_file_key';

/** Database & cloud connectors stay visible but cannot be selected (local CSV upload only). */
const DISABLE_DATABASE_CLOUD_INTEGRATIONS = true;

function stagedChunkedFileMeta(f: File): string {
  return `${f.name}|${f.size}|${f.lastModified}`;
}

function persistStagedChunkedUpload(file: File, datasetId: string): void {
  try {
    sessionStorage.setItem(STAGED_CHUNKED_DATASET_ID_KEY, datasetId);
    sessionStorage.setItem(STAGED_CHUNKED_FILE_META_KEY, stagedChunkedFileMeta(file));
  } catch {
    /* ignore */
  }
}

function clearStagedChunkedUploadIfFileMatches(file: File): void {
  try {
    if (sessionStorage.getItem(STAGED_CHUNKED_FILE_META_KEY) !== stagedChunkedFileMeta(file)) return;
    sessionStorage.removeItem(STAGED_CHUNKED_DATASET_ID_KEY);
    sessionStorage.removeItem(STAGED_CHUNKED_FILE_META_KEY);
  } catch {
    /* ignore */
  }
}

export type PartitionRole = 'full' | 'train' | 'test' | 'oot';

interface Step1ObjectivesDataProps {
  selectedDataSources: any[];
  onDataSourceSelect: (dataSource: any) => void;
  onRemoveDataSource: (index: number) => void;
  onUpdateFilePartition?: (ingestionId: string, role: PartitionRole) => void;
  showDataSourceSelectionModal: boolean;
  setShowDataSourceSelectionModal: (show: boolean) => void;

  datasetAnalysis: {
    columns: any[];
    suggestedTargetVariable: string | null;
    totalRows: number;
    totalColumns: number;
  } | null;
  setDatasetAnalysis?: (analysis: {
    columns: any[];
    suggestedTargetVariable: string | null;
    totalRows: number;
    totalColumns: number;
  } | null) => void;
  isAnalyzingDataset: boolean;
  isUploadingDataset: boolean;
  /**
   * P1.2: Tracks the post-Submit background dataset-type-classification job.
   * Drives the ML-Problem-Type spinner only; does NOT gate the Submit button
   * (kept separate from `isAnalyzingDataset` which covers the pre-Submit
   * `/analyze-dataset` call). Optional for backward compatibility.
   */
  mlClassificationPending?: boolean;

  datasetConfig: {
    target_variable: string;
    target_variable_type: 'Numerical' | 'Categorical';
    dataset_structure_type: 'classification' | 'regression' | 'time_series' | 'others';
    problem_statement: string;
    data_dictionary: string;
    unique_id_combinations: string[];
    segmentation_variable: string;
    weight_variable: string;
    sample_identifier_variable: string;
  } | null;
  setDatasetConfig: (config: any) => void;

  activeDatasetId: string | null;
  /** Set after successful upload while the dataset ID alert is open; keeps Step 1 in “post-submit” state. */
  pendingDatasetId?: string | null;
  setActiveDatasetId: (id: string | null) => void;

  showDatasetOverview: boolean;
  setShowDatasetOverview: (show: boolean) => void;

  chatInputs: { [key: number]: string };
  setChatInputs: (inputs: any) => void;

  dataDictionaryFile: File | null;
  setDataDictionaryFile: (file: File | null) => void;
  onDataDictionaryFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveDataDictionaryFile: () => void;

  onSubmitDataset: () => Promise<void>;
  canSubmitDataset?: boolean;
  submitValidationError?: string | null;
  submitBlockedReason?: string;

  // Staged user knowledge (Objectives)
  stagedUserKnowledgeFiles: File[];
  setStagedUserKnowledgeFiles: (files: File[]) => void;
  stagedUseAcrossMidas: boolean;
  setStagedUseAcrossMidas: (value: boolean) => void;
  stagedUseExlExpertise: boolean;
  setStagedUseExlExpertise: (value: boolean) => void;

  /** Whether the user has proceeded past the data upload section */
  hasProceededToConfig: boolean;
  setHasProceededToConfig: (value: boolean) => void;
  /** Called when user clicks Proceed - triggers finalize/combine for pre-split */
  onProceedToConfig: () => Promise<void>;
  isProceedingToConfig?: boolean;

  // ML classification result passed as React state so the UI updates the instant
  // the LLM responds - no sessionStorage polling needed.
  mlClassificationResult?: {
    dataset_type: string;
    confidence: number;
    reasoning: string;
    characteristics: Record<string, string>;
    recommendations: string[];
  } | null;
  mlClassificationError?: string | null;
}

/** Compact badge text on uploaded file rows (matches product mock). */
const ROW_BADGE_LABELS: Record<PartitionRole, string> = {
  full: 'Full population',
  train: 'Train',
  test: 'Test',
  oot: 'Validation',
};

/** Full labels on tag picker pills */
const PILL_LABELS: Record<PartitionRole, string> = {
  full: 'Full population',
  train: 'Train',
  test: 'Test',
  oot: 'Validation',
};

/** Badge colors aligned with product mock: Train blue, Test green, OOT peach. */
const ROLE_COLORS: Record<PartitionRole, { bg: string; text: string; border: string }> = {
  full: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200' },
  train: { bg: 'bg-sky-100', text: 'text-sky-800', border: 'border-sky-200' },
  test: { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200' },
  oot: { bg: 'bg-amber-100', text: 'text-amber-900', border: 'border-amber-200' },
};

const CheckboxMultiselect: React.FC<{
  options: { name: string; type: string; logical_type?: string; is_date?: boolean }[];
  selectedValues: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
  disabled?: boolean;
}> = ({ options, selectedValues, onChange, placeholder, disabled = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (disabled) return;
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchQuery('');
        setIsTyping(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [disabled]);

  useEffect(() => {
    if (!disabled) return;
    setIsOpen(false);
    setSearchQuery('');
    setIsTyping(false);
  }, [disabled]);

  const handleCheckboxChange = (value: string) => {
    if (disabled) return;
    if (selectedValues.includes(value)) {
      onChange(selectedValues.filter((v) => v !== value));
    } else {
      onChange([...selectedValues, value]);
    }
  };

  const filteredOptions = options.filter((option) =>
    option.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const displayText =
    selectedValues.length === 0
      ? placeholder
      : selectedValues.length === 1
        ? selectedValues[0]
        : `${selectedValues.length} variables selected`;

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          disabled={disabled}
          value={isTyping ? searchQuery : displayText}
          onChange={(e) => {
            if (disabled) return;
            setSearchQuery(e.target.value);
            setIsOpen(true);
            setIsTyping(true);
          }}
          onFocus={() => {
            if (disabled) return;
            setIsOpen(true);
            setIsTyping(true);
            inputRef.current?.select();
          }}
          onBlur={() => {
            setTimeout(() => {
              setIsTyping(false);
              setSearchQuery('');
            }, 200);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setIsOpen(false);
              setSearchQuery('');
              setIsTyping(false);
              inputRef.current?.blur();
            }
          }}
          placeholder={placeholder}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left pr-8 disabled:opacity-60 disabled:cursor-not-allowed"
        />
        <ChevronDown 
          className={`absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 pointer-events-none transition-transform text-gray-500 dark:text-gray-400 ${isOpen ? 'rotate-180' : ''}`}
        />
      </div>
      {isOpen && !disabled && (
        <div className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-60 overflow-hidden flex flex-col">
          {/* Options list - scrollable */}
          <div className="overflow-y-auto max-h-60">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-2 text-gray-500 dark:text-gray-400 text-sm">
                {options.length === 0 ? 'No options available' : 'No options found'}
              </div>
            ) : (
              filteredOptions.map((option) => {
                const isDate = option.logical_type === 'Date' || option.is_date;
                const displayType = isDate ? 'Date' : option.type;
                return (
                  <div
                    key={option.name}
                    className="flex items-center px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/60"
                  >
                    <label
                      className="flex items-center cursor-pointer w-full"
                      onMouseDown={(event) => event.preventDefault()}
                    >
                      <input
                        type="checkbox"
                        checked={selectedValues.includes(option.name)}
                        onChange={() => handleCheckboxChange(option.name)}
                        className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-500 rounded bg-white dark:bg-gray-700"
                      />
                      <span className="text-sm text-gray-900 dark:text-gray-100">
                        {option.name} <span className="text-gray-500 dark:text-gray-400">({displayType})</span>
                      </span>
                    </label>
                  </div>
                );
              })
            )}
          </div>
          {selectedValues.length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-600 px-3 py-2 sticky bottom-0 bg-white dark:bg-gray-800">
              <button
                type="button"
                onClick={() => onChange([])}
                className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
              >
                Clear all selections
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function isPartitionRole(v: unknown): v is PartitionRole {
  return v === 'full' || v === 'train' || v === 'test' || v === 'oot';
}

interface ColumnInfo {
  name: string;
  type: string;
  logicalType?: string;
}

interface UploadRow {
  id: string;
  file: File;
  role?: PartitionRole;
  rowCount?: number;
  colCount?: number;
  columns?: ColumnInfo[];
  isAnalyzing?: boolean;
  uploadProgress?: number;
  uploadedDatasetId?: string;
  uploadError?: string;
}

interface SchemaValidationResult {
  isValid: boolean;
  errors: SchemaError[];
}

interface SchemaError {
  type: 'column_count' | 'column_name' | 'data_type';
  message: string;
  details?: {
    file1?: string;
    file2?: string;
    count1?: number;
    count2?: number;
    missingColumns?: string[];
    extraColumns?: string[];
    commonColumns?: string[];
    typeMismatches?: Array<{
      column: string;
      type1: string;
      type2: string;
      file1: string;
      file2: string;
    }>;
  };
}

// Schema Validation Errors Component
const SchemaValidationErrors: React.FC<{ errors: SchemaError[] }> = ({ errors }) => {
  const [expandedErrors, setExpandedErrors] = useState<Set<number>>(new Set());

  const toggleError = (index: number) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (errors.length === 0) return null;

  return (
    <div className="space-y-3">
      {errors.map((error, index) => (
        <div
          key={index}
          className="border border-red-200 bg-red-50 rounded-lg overflow-hidden"
        >
          <button
            type="button"
            onClick={() => toggleError(index)}
            className="w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-red-100 transition-colors"
          >
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-red-800">{error.message}</p>
              {error.details && (
                <p className="text-xs text-red-600 mt-1">
                  Click to {expandedErrors.has(index) ? 'hide' : 'show'} details
                </p>
              )}
            </div>
            <ChevronDown
              className={`h-5 w-5 text-red-400 transition-transform ${
                expandedErrors.has(index) ? 'rotate-180' : ''
              }`}
            />
          </button>

          {expandedErrors.has(index) && error.details && (
            <div className="px-4 pb-4 border-t border-red-200 bg-red-50/50">
              {/* Column Count Mismatch Details */}
              {error.type === 'column_count' && (
                <div className="mt-3 text-sm">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-2 bg-white rounded border border-red-100">
                      <p className="text-xs text-gray-500 truncate" title={error.details.file1}>{error.details.file1}</p>
                      <p className="font-semibold text-gray-900">{error.details.count1} columns</p>
                    </div>
                    <div className="p-2 bg-white rounded border border-red-100">
                      <p className="text-xs text-gray-500 truncate" title={error.details.file2}>{error.details.file2}</p>
                      <p className="font-semibold text-gray-900">{error.details.count2} columns</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Column Name Mismatch Details */}
              {error.type === 'column_name' && (
                <div className="mt-3 space-y-3 text-sm">
                  {error.details.missingColumns && error.details.missingColumns.length > 0 && (
                    <div>
                      <p className="font-medium text-red-700 mb-1">
                        Missing in {error.details.file2} (present in {error.details.file1}):
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {error.details.missingColumns.map((col) => (
                          <span
                            key={col}
                            className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-mono"
                          >
                            {col}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {error.details.extraColumns && error.details.extraColumns.length > 0 && (
                    <div>
                      <p className="font-medium text-amber-700 mb-1">
                        Extra in {error.details.file2} (not in {error.details.file1}):
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {error.details.extraColumns.map((col) => (
                          <span
                            key={col}
                            className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-mono"
                          >
                            {col}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {error.details.commonColumns && error.details.commonColumns.length > 0 && (
                    <div>
                      <p className="font-medium text-green-700 mb-1">
                        Common columns ({error.details.commonColumns.length}):
                      </p>
                      <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                        {error.details.commonColumns.map((col) => (
                          <span
                            key={col}
                            className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-mono"
                          >
                            {col}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Data Type Mismatch Details */}
              {error.type === 'data_type' && error.details.typeMismatches && (
                <div className="mt-3">
                  <p className="font-medium text-red-700 mb-2 text-sm">Type mismatches:</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="bg-red-100">
                          <th className="text-left py-1.5 px-2 font-medium text-red-800 border-b border-red-200">Column</th>
                          <th className="text-left py-1.5 px-2 font-medium text-red-800 border-b border-red-200">{error.details.file1}</th>
                          <th className="text-left py-1.5 px-2 font-medium text-red-800 border-b border-red-200">{error.details.file2}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {error.details.typeMismatches.map((mismatch, i) => (
                          <tr key={i} className="border-b border-red-100 last:border-0">
                            <td className="py-1.5 px-2 font-mono text-gray-900">{mismatch.column}</td>
                            <td className="py-1.5 px-2 text-blue-600">{mismatch.type1}</td>
                            <td className="py-1.5 px-2 text-red-600">{mismatch.type2}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

type SplitConfirmationStats = {
  trainRows: number;
  testRows: number;
  validationRows: number;
  trainEventRate: number | null;
  testEventRate: number | null;
  validationEventRate: number | null;
};

/** Restore confirmed split state after refresh from `dataset_config` in sessionStorage. */
function readSplitConfirmationHydrationFromSession(): {
  isConfirmed: boolean;
  currentStep: number;
  stats: SplitConfirmationStats | null;
} {
  if (typeof window === 'undefined') {
    return { isConfirmed: false, currentStep: 0, stats: null };
  }
  try {
    const raw = sessionStorage.getItem('dataset_config');
    if (!raw) return { isConfirmed: false, currentStep: 0, stats: null };
    const cfg = JSON.parse(raw) as { split_configuration?: { confirmed?: boolean; partition_stats?: Record<string, { rows?: number }> } };
    const sc = cfg?.split_configuration;
    if (sc && sc.confirmed === true && sc.partition_stats) {
      const ps = sc.partition_stats;
      return {
        isConfirmed: true,
        currentStep: 6,
        stats: {
          trainRows: Number(ps.train?.rows) || 0,
          testRows: Number(ps.test?.rows) || 0,
          validationRows: Number(ps.validation?.rows) || 0,
          trainEventRate: null,
          testEventRate: null,
          validationEventRate: null,
        },
      };
    }
  } catch {
    /* ignore */
  }
  return { isConfirmed: false, currentStep: 0, stats: null };
}

const Step1ObjectivesData: React.FC<Step1ObjectivesDataProps> = ({
  selectedDataSources,
  onDataSourceSelect,
  onRemoveDataSource,
  onUpdateFilePartition,
  showDataSourceSelectionModal,
  setShowDataSourceSelectionModal,
  datasetAnalysis,
  setDatasetAnalysis,
  isAnalyzingDataset,
  isUploadingDataset,
  mlClassificationPending = false,
  datasetConfig,
  setDatasetConfig,
  activeDatasetId,
  pendingDatasetId = null,
  setActiveDatasetId,
  showDatasetOverview: _showDatasetOverview,
  setShowDatasetOverview,
  chatInputs,
  setChatInputs,
  dataDictionaryFile,
  setDataDictionaryFile: _setDataDictionaryFile,
  onDataDictionaryFileSelect,
  onRemoveDataDictionaryFile,
  onSubmitDataset,
  canSubmitDataset = true,
  submitValidationError = null,
  submitBlockedReason,
  stagedUserKnowledgeFiles,
  setStagedUserKnowledgeFiles,
  stagedUseAcrossMidas,
  setStagedUseAcrossMidas,
  stagedUseExlExpertise,
  setStagedUseExlExpertise,
  hasProceededToConfig,
  setHasProceededToConfig,
  onProceedToConfig,
  isProceedingToConfig = false,
  mlClassificationResult,
  mlClassificationError,
}) => {
  const [uniqueIdWarning, setUniqueIdWarning] = useState<string | null>(null);
  const [isValidatingUniqueIds, setIsValidatingUniqueIds] = useState(false);
  const uniqueValidateAbortRef = useRef<AbortController | null>(null);
  const uniqueValidateDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Client-side result cache for the unique-ID validation hot path. Same
  // (datasetId, sortedCols) tuple within a single browser tab returns
  // instantly without round-tripping the backend - matters when the user
  // toggles selections off and on while staring at a 2 GB dataset.
  // Persisted in sessionStorage and scoped by user id so the cache is dropped
  // across logouts.
  const uniqueIdValidationCacheRef = useRef<
    Map<string, { warning: string | null; cachedAt: number }>
  >(new Map());
  const uniqueIdCacheStorageKey = useMemo(() => {
    let userId: string | number | null = null;
    try {
      const raw = localStorage.getItem('user_data');
      if (raw) {
        const parsed = JSON.parse(raw) as { id?: number | string };
        userId = parsed?.id ?? null;
      }
    } catch {
      userId = null;
    }
    return `unique_id_validation_cache_v1::${userId ?? 'anon'}`;
  }, []);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(uniqueIdCacheStorageKey);
      if (!raw) return;
      const obj = JSON.parse(raw) as Record<
        string,
        { warning: string | null; cachedAt: number }
      >;
      uniqueIdValidationCacheRef.current = new Map(Object.entries(obj));
    } catch {
      uniqueIdValidationCacheRef.current = new Map();
    }
  }, [uniqueIdCacheStorageKey]);

  const persistUniqueIdValidationCache = useCallback(() => {
    try {
      const obj: Record<string, { warning: string | null; cachedAt: number }> = {};
      uniqueIdValidationCacheRef.current.forEach((v, k) => {
        obj[k] = v;
      });
      sessionStorage.setItem(uniqueIdCacheStorageKey, JSON.stringify(obj));
    } catch {
      // sessionStorage full / unavailable - in-memory cache still works.
    }
  }, [uniqueIdCacheStorageKey]);

  const { updateModelObjective } = useDocumentation();

  useEffect(() => {
    return () => {
      if (uniqueValidateDebounceRef.current) clearTimeout(uniqueValidateDebounceRef.current);
      uniqueValidateAbortRef.current?.abort();
    };
  }, []);

  const [uploadedRows, setUploadedRows] = useState<UploadRow[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const analyzeStartedRef = useRef<Set<string>>(new Set());
  const chunkStartedRef = useRef<Set<string>>(new Set());
  const [exclusionRules, setExclusionRules] = useState<ExclusionGroup[]>([]);
  const [filteredRowCount, setFilteredRowCount] = useState<number | null>(null);
  const [originalRowCount, setOriginalRowCount] = useState<number | null>(null);
  
  // Variable review state
  const [showVariableReview, setShowVariableReview] = useState(false);
  const [variableReviewCompleted, setVariableReviewCompleted] = useState(false);
  const [removedVariables, setRemovedVariables] = useState<string[]>([]);

  // Integration state (for database/cloud integrations)
  const [selectedIntegration, setSelectedIntegration] = useState<IntegrationDataSource | null>(null);
  const [integrationConfigData, setIntegrationConfigData] = useState<Record<string, string>>({});
  const [integrationValidationErrors, setIntegrationValidationErrors] = useState<string[]>([]);
  const [showIntegrationPassword, setShowIntegrationPassword] = useState(false);

  // Memoized callback for filtered row count changes to prevent infinite re-renders
  const handleFilteredRowsChange = useCallback((rows: number) => {
    setFilteredRowCount(rows);
    // Update datasetAnalysis with filtered row count
    if (setDatasetAnalysis && datasetAnalysis) {
      setDatasetAnalysis({ ...datasetAnalysis, totalRows: rows });
    }
    // Store filtered row count in sessionStorage
    try {
      const cfg = sessionStorage.getItem('dataset_config');
      const parsed = cfg ? JSON.parse(cfg) : {};
      parsed.filtered_row_count = rows;
      sessionStorage.setItem('dataset_config', JSON.stringify(parsed));
    } catch (e) {
      console.error('Failed to save filtered row count:', e);
    }
  }, [setDatasetAnalysis, datasetAnalysis]);

  // Split confirmation state (hydrate from session so Confirm stays hidden after refresh)
  const [splitConfirmationState, setSplitConfirmationState] = useState<{
    isConfirming: boolean;
    isConfirmed: boolean;
    currentStep: number;
    error: string | null;
    stats: SplitConfirmationStats | null;
  }>(() => {
    const h = readSplitConfirmationHydrationFromSession();
    return {
      isConfirming: false,
      isConfirmed: h.isConfirmed,
      currentStep: h.currentStep,
      error: null,
      stats: h.stats,
    };
  });

  useEffect(() => {
    const onDatasetConfigChanged = () => {
      const h = readSplitConfirmationHydrationFromSession();
      if (!h.isConfirmed) return;
      setSplitConfirmationState((prev) => ({
        ...prev,
        isConfirmed: true,
        isConfirming: false,
        currentStep: 6,
        error: null,
        stats: h.stats ?? prev.stats,
      }));
    };
    window.addEventListener('datasetConfigChanged', onDatasetConfigChanged);
    return () => window.removeEventListener('datasetConfigChanged', onDatasetConfigChanged);
  }, []);

  // Update partition stats when filtered row count changes (separate effect to avoid callback dependency issues)
  useEffect(() => {
    if (filteredRowCount === null) return;
    if (!splitConfirmationState.isConfirmed || !splitConfirmationState.stats) return;
    
    try {
      const ratiosRaw = sessionStorage.getItem('dataset_config');
      const ratiosParsed = ratiosRaw ? JSON.parse(ratiosRaw) : {};
      const sc = ratiosParsed.split_configuration;
      if (sc && sc.train_pct !== undefined) {
        const trainPct = sc.train_pct || 80;
        const testPct = sc.test_pct || 10;
        const newTrainRows = Math.round(filteredRowCount * trainPct / 100);
        const newTestRows = Math.round(filteredRowCount * testPct / 100);
        const newValidationRows = filteredRowCount - newTrainRows - newTestRows;
        setSplitConfirmationState((prev) => ({
          ...prev,
          stats: prev.stats ? {
            ...prev.stats,
            trainRows: newTrainRows,
            testRows: newTestRows,
            validationRows: newValidationRows,
          } : null,
        }));
      }
    } catch (e) {
      console.error('Failed to update split stats:', e);
    }
  }, [filteredRowCount, splitConfirmationState.isConfirmed]);

  const hasStagedDataset = selectedDataSources.some(
    (source) => source?.type === 'file' && source?.file instanceof File
  );

  const effectiveTargetVar = (
    datasetConfig?.target_variable ||
    (chatInputs['target_var' as unknown as number] as unknown as string) ||
    ''
  ).trim();

  const rawTargetVariableType = (
    datasetConfig?.target_variable_type ||
    (chatInputs['target_type' as unknown as number] as unknown as string) ||
    ''
  ).trim();
  const hasValidTargetVariableType =
    rawTargetVariableType === 'Numerical' || rawTargetVariableType === 'Categorical';

  const uniqueIdsForObjectives = (() => {
    const fromCfg = datasetConfig?.unique_id_combinations;
    if (Array.isArray(fromCfg) && fromCfg.filter(Boolean).length > 0) {
      return fromCfg.filter(Boolean) as string[];
    }
    const fromChat = chatInputs['unique_id_combinations' as unknown as number] as unknown as string[] | undefined;
    if (Array.isArray(fromChat)) return fromChat.filter(Boolean) as string[];
    return [];
  })();

  const hasRequiredObjectiveFields =
    Boolean(effectiveTargetVar) && hasValidTargetVariableType && uniqueIdsForObjectives.length > 0;

  const objectivesFormLocked = splitConfirmationState.isConfirmed;

  const showPostSubmitMlSection = Boolean(activeDatasetId || pendingDatasetId);

  const aiProblemTypeHint = useMemo(() => {
    if (!showPostSubmitMlSection || typeof window === 'undefined') return null;
    try {
      const raw = sessionStorage.getItem('dataset_classification');
      if (!raw) return null;
      const o = JSON.parse(raw) as {
        dataset_type?: string;
        confidence?: number;
        reasoning?: string;
        target_variable?: string;
      };
      if (!o.dataset_type || o.confidence == null) return null;
      if (effectiveTargetVar && o.target_variable && o.target_variable !== effectiveTargetVar) return null;
      return o;
    } catch {
      return null;
    }
  }, [showPostSubmitMlSection, effectiveTargetVar, datasetConfig?.dataset_structure_type, isAnalyzingDataset, mlClassificationPending]);

  const mlClassificationErrorMessage = useMemo(() => {
    if (!showPostSubmitMlSection || typeof window === 'undefined') return null;
    if (aiProblemTypeHint) return null;
    try {
      const raw = sessionStorage.getItem('dataset_classification_error');
      if (!raw) return null;
      const o = JSON.parse(raw) as { message?: string };
      return o?.message ?? null;
    } catch {
      return null;
    }
  }, [showPostSubmitMlSection, aiProblemTypeHint, isAnalyzingDataset, mlClassificationPending]);

  const getDisplayType = (column: any): string => {
    if (column?.logical_type === 'Date' || column?.is_date) return 'Date';
    return column?.logical_type || column?.type || '';
  };

  const mapColumnToVariableCategory = (column: any): 'Numerical' | 'Categorical' => {
    const t = getDisplayType(column);
    if (t === 'Numerical') return 'Numerical';
    return 'Categorical';
  };

  const runValidateUniqueIds = useCallback(
    async (selectedColumns: string[]) => {
      if (!selectedColumns || selectedColumns.length === 0) {
        setUniqueIdWarning(null);
        return;
      }
      uniqueValidateAbortRef.current?.abort();
      const ac = new AbortController();
      uniqueValidateAbortRef.current = ac;

      const fileSource = selectedDataSources.find((s) => s?.type === 'file' && s?.file instanceof File);
      const file = fileSource?.file as File | undefined;
      const row = file ? uploadedRows.find(r => r.file === file) : undefined;
      const serverDatasetId = activeDatasetId ?? pendingDatasetId ?? row?.uploadedDatasetId ?? null;

      // We always validate by dataset_id - the legacy multipart re-upload
      // path was removed because it forced a 2 GB round-trip every time the
      // user toggled a column.
      if (!serverDatasetId) {
        if (row?.uploadError) {
          setUniqueIdWarning(
            `Upload failed for ${row.file.name}. Please re-upload the file before validating unique IDs.`
          );
          return;
        }
        if (row && (row.uploadProgress ?? 0) < 100) {
          setUniqueIdWarning(
            'Please wait for the file upload to complete before validating unique IDs.'
          );
        }
        return;
      }

      const sortedCols = [...selectedColumns].sort();
      const cacheKey = `${serverDatasetId}|${sortedCols.join('|')}`;
      const cached = uniqueIdValidationCacheRef.current.get(cacheKey);
      if (cached) {
        setUniqueIdWarning(cached.warning);
        return;
      }

      setIsValidatingUniqueIds(true);
      try {
        const result = await fastApiService.validateUniqueIdsById(
          serverDatasetId,
          selectedColumns,
          { signal: ac.signal }
        );

        if (ac.signal.aborted) return;

        let warning: string | null = null;
        if (result.success && !result.is_unique) {
          warning = `Selected columns (${selectedColumns.join(', ')}) cannot act as unique key. Found ${result.duplicate_count} duplicate rows out of ${result.total_rows} total rows.`;
        }
        // Cache only successful answers - error responses (missing column,
        // backend 5xx) should retry on the next selection change.
        if (result.success) {
          uniqueIdValidationCacheRef.current.set(cacheKey, {
            warning,
            cachedAt: Date.now(),
          });
          persistUniqueIdValidationCache();
        }
        setUniqueIdWarning(warning);
      } catch (e: unknown) {
        const aborted =
          (e instanceof Error && e.name === 'AbortError') ||
          (typeof DOMException !== 'undefined' && e instanceof DOMException && e.name === 'AbortError');
        if (aborted) return;
        setUniqueIdWarning('Failed to validate unique IDs. Please try again.');
      } finally {
        if (uniqueValidateAbortRef.current === ac) {
          setIsValidatingUniqueIds(false);
        }
      }
    },
    [activeDatasetId, pendingDatasetId, selectedDataSources, uploadedRows, persistUniqueIdValidationCache]
  );

  /** Debounced so rapid multiselect changes do not queue many huge uploads / scans. */
  const validateUniqueIds = (selectedColumns: string[]) => {
    if (uniqueValidateDebounceRef.current) clearTimeout(uniqueValidateDebounceRef.current);
    if (!selectedColumns || selectedColumns.length === 0) {
      uniqueValidateAbortRef.current?.abort();
      setIsValidatingUniqueIds(false);
      setUniqueIdWarning(null);
      return;
    }
    uniqueValidateDebounceRef.current = setTimeout(() => {
      void runValidateUniqueIds(selectedColumns);
    }, 400);
  };

  useEffect(() => {
    const fileEntries = selectedDataSources.filter((s) => s?.type === 'file' && s?.file instanceof File);
    setUploadedRows((prev) => {
      const prevById = new Map(prev.map((r) => [r.id, r]));
      return fileEntries.map((s: any, idx: number) => {
        const id =
          s.ingestionId ||
          `legacy-${idx}-${s.file.name}-${s.file.size}-${s.file.lastModified}`;
        const old = prevById.get(id);
        const role = isPartitionRole(s.partitionRole)
          ? s.partitionRole
          : isPartitionRole(old?.role)
            ? old?.role
            : undefined;
        return {
          id,
          file: s.file as File,
          role,
          rowCount: old?.rowCount,
          colCount: old?.colCount,
          columns: old?.columns,
          isAnalyzing: old?.isAnalyzing ?? false,
          uploadProgress: old?.uploadProgress,
          uploadedDatasetId: old?.uploadedDatasetId,
          uploadError: old?.uploadError,
        };
      });
    });
  }, [selectedDataSources]);

  // Capture original row count when datasetAnalysis is first set
  useEffect(() => {
    if (datasetAnalysis && originalRowCount === null) {
      setOriginalRowCount(datasetAnalysis.totalRows);
    }
  }, [datasetAnalysis, originalRowCount]);

  useEffect(() => {
    uploadedRows.forEach((row) => {
      // 1. Analyze Dataset
      if (row.rowCount == null && !analyzeStartedRef.current.has(row.id)) {
        analyzeStartedRef.current.add(row.id);
        setUploadedRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, isAnalyzing: true } : r)));
        fastApiService
          .analyzeDataset({ file: row.file })
          .then((res) => {
            setUploadedRows((prev) =>
              prev.map((r) =>
                r.id === row.id
                  ? {
                      ...r,
                      rowCount: res?.success ? res.dataset_info.total_rows : r.rowCount,
                      colCount: res?.success ? res.dataset_info.total_columns : r.colCount,
                      columns: res?.success
                        ? res.dataset_info.columns.map((col) => ({
                            name: col.name,
                            type: col.type,
                            logicalType: col.logical_type || col.type,
                          }))
                        : r.columns,
                      isAnalyzing: false,
                    }
                  : r
              )
            );
          })
          .catch(() => {
            setUploadedRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, isAnalyzing: false } : r)));
          });
      }

      // 2. Chunked Upload for faster previews
      if (!chunkStartedRef.current.has(row.id) && !row.uploadedDatasetId) {
        chunkStartedRef.current.add(row.id);
        setUploadedRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, uploadProgress: 0 } : r)));
        
        fastApiService
          .chunkedUpload(row.file, (sent, total) => {
            const pct = total > 0 ? Math.round((sent / total) * 100) : 0;
            setUploadedRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, uploadProgress: pct } : r)));
          })
          .then((res) => {
            persistStagedChunkedUpload(row.file, res.dataset_id);
            setUploadedRows((prev) =>
              prev.map((r) =>
                r.id === row.id
                  ? { ...r, uploadProgress: 100, uploadedDatasetId: res.dataset_id, uploadError: undefined }
                  : r
              )
            );
          })
          .catch((err: unknown) => {
            clearStagedChunkedUploadIfFileMatches(row.file);
            const msg = err instanceof Error ? err.message : 'Chunked upload failed';
            setUploadedRows((prev) =>
              prev.map((r) =>
                r.id === row.id
                  ? { ...r, uploadError: msg, uploadProgress: 0 }
                  : r
              )
            );
          });
      }
    });
  }, [uploadedRows]);

  const usedRoles = useMemo(() => {
    const r = new Set<PartitionRole>();
    const roleCounts: Record<string, number> = {};
    selectedDataSources.forEach((s) => {
      if (s?.type === 'file' && isPartitionRole(s.partitionRole)) {
        const role = s.partitionRole as PartitionRole;
        roleCounts[role] = (roleCounts[role] || 0) + 1;
        // For 'oot' (validation), allow up to 3 files; for others, only 1
        const maxAllowed = role === 'oot' ? 3 : 1;
        if (roleCounts[role] >= maxAllowed) {
          r.add(role);
        }
      }
    });
    return r;
  }, [selectedDataSources]);

  const workflowPath = useMemo<'platform_split' | 'pre_split' | 'conflict' | null>(() => {
    const files = selectedDataSources.filter((s) => s?.type === 'file' && isPartitionRole(s.partitionRole));
    if (files.length === 0) return null;
    const hasFull = files.some((s) => s.partitionRole === 'full');
    const hasPart = files.some((s) => {
      const p = s.partitionRole;
      return p === 'train' || p === 'test' || p === 'oot';
    });
    if (hasFull && hasPart) return 'conflict';
    if (hasFull) return 'platform_split';
    if (hasPart) return 'pre_split';
    return null;
  }, [selectedDataSources]);

  /** Block Proceed until chunked upload reaches 100% and local analyze finishes (rows/cols shown). */
  const proceedToConfigBlockedByRowPipeline = useMemo(
    () =>
      uploadedRows.some(
        (row) =>
          !row.uploadError &&
          (((row.uploadProgress ?? 0) < 100) || row.isAnalyzing === true),
      ),
    [uploadedRows],
  );

  const validationErrors = useMemo(() => {
    const errors: string[] = [];
    const files = selectedDataSources.filter((s) => s?.type === 'file');
    const roles = files.filter((s) => isPartitionRole(s.partitionRole)).map((s) => s.partitionRole as PartitionRole);
    const count = (role: PartitionRole) => roles.filter((x) => x === role).length;
    if (count('full') > 1) errors.push('Only one full population dataset is allowed.');
    if (count('train') > 1) errors.push('Only one Train dataset is allowed.');
    if (count('test') > 1) errors.push('Only one Test dataset is allowed.');
    if (count('oot') > 3) errors.push('Maximum 3 Validation datasets are allowed.');
    if (workflowPath === 'conflict') {
      errors.push('Cannot combine full dataset with individual partitions. Please remove one or the other.');
    }
    if (workflowPath === 'pre_split') {
      const hasTrain = selectedDataSources.some((s) => s?.type === 'file' && s.partitionRole === 'train');
      if (!hasTrain) {
        errors.push('A training (development) dataset is required when using pre-split datasets.');
      }
    }
    return errors;
  }, [selectedDataSources, workflowPath]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) handleLocalFile(e.dataTransfer.files[0]);
  };

  const handleLocalFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      alert('Only CSV files are supported.');
      return;
    }
    const ingestionId = `ing-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
    onDataSourceSelect({
      type: 'file',
      file,
      ingestionId,
    });
  };

  const handleAssignTagForRow = (ingestionId: string, role: PartitionRole) => {
    const countForRole = selectedDataSources.filter(
      (s: any) =>
        s?.type === 'file' &&
        s.ingestionId !== ingestionId &&
        isPartitionRole(s.partitionRole) &&
        s.partitionRole === role
    ).length;
    
    const maxAllowed = role === 'oot' ? 3 : 1;
    if (countForRole >= maxAllowed) {
      const roleName = role === 'oot' ? 'Validation' : role === 'full' ? 'Full population' : role.charAt(0).toUpperCase() + role.slice(1);
      alert(`Maximum ${maxAllowed} ${roleName} dataset${maxAllowed > 1 ? 's are' : ' is'} allowed.`);
      return;
    }
    onUpdateFilePartition?.(ingestionId, role);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleLocalFile(f);
    e.target.value = '';
  };

  const handleRemoveRow = (id: string) => {
    const row = uploadedRows.find((r) => r.id === id);
    if (row) clearStagedChunkedUploadIfFileMatches(row.file);
    chunkStartedRef.current.delete(id);
    analyzeStartedRef.current.delete(id);
    const idx = selectedDataSources.findIndex((s: any) => s?.ingestionId === id);
    if (idx >= 0) onRemoveDataSource(idx);
    else {
      const rowLegacy = uploadedRows.find((r) => r.id === id);
      if (rowLegacy) {
        const i = selectedDataSources.findIndex(
          (s: any) => s?.type === 'file' && s?.file?.name === rowLegacy.file.name && s?.file?.size === rowLegacy.file.size
        );
        if (i >= 0) onRemoveDataSource(i);
      }
    }
  };

  // Integration selection handlers (inline, no modal)
  const handleIntegrationSelect = (source: IntegrationDataSource) => {
    if (DISABLE_DATABASE_CLOUD_INTEGRATIONS) return;
    if (selectedIntegration?.id === source.id) {
      setSelectedIntegration(null);
      setIntegrationConfigData({});
      setIntegrationValidationErrors([]);
      return;
    }
    setSelectedIntegration(source);
    const strategy = getConnectionStrategy(source.id);
    setIntegrationConfigData(strategy.getInitialConfig());
    setIntegrationValidationErrors([]);
  };

  const handleIntegrationConfigChange = (field: string, value: string) => {
    setIntegrationConfigData(prev => ({ ...prev, [field]: value }));
    setIntegrationValidationErrors([]);
  };

  const handleIntegrationConnect = () => {
    if (DISABLE_DATABASE_CLOUD_INTEGRATIONS) return;
    if (!selectedIntegration) return;
    
    const strategy = getConnectionStrategy(selectedIntegration.id);
    const validation = strategy.validate(integrationConfigData);
    
    if (!validation.valid) {
      setIntegrationValidationErrors(validation.errors);
      return;
    }
    
    onDataSourceSelect({
      type: selectedIntegration.type,
      source: selectedIntegration,
      config: integrationConfigData,
    });
    setSelectedIntegration(null);
    setIntegrationConfigData({});
    setIntegrationValidationErrors([]);
  };

  const handleIntegrationCancel = () => {
    setSelectedIntegration(null);
    setIntegrationConfigData({});
    setIntegrationValidationErrors([]);
  };

  const fileCount = selectedDataSources.filter((s) => s?.type === 'file').length;

  const hasUntaggedFiles = useMemo(
    () => selectedDataSources.some((s) => s?.type === 'file' && !isPartitionRole(s.partitionRole)),
    [selectedDataSources]
  );

  const canProceed = fileCount > 0 && validationErrors.length === 0 && !hasUntaggedFiles;

  const taggedRowsWithCounts = useMemo(
    () => uploadedRows.filter((r) => r.role && r.rowCount != null && !r.isAnalyzing),
    [uploadedRows]
  );

  // Comprehensive schema validation for pre-split uploads
  const schemaValidation = useMemo((): SchemaValidationResult => {
    // Only validate for pre-split with multiple files
    if (workflowPath !== 'pre_split' || taggedRowsWithCounts.length < 2) {
      return { isValid: true, errors: [] };
    }

    // Use train as reference, or first file if no train
    const referenceRow = taggedRowsWithCounts.find((r) => r.role === 'train') || taggedRowsWithCounts[0];
    if (!referenceRow.columns || referenceRow.columns.length === 0) {
      return { isValid: true, errors: [] }; // Still analyzing
    }

    const errors: SchemaError[] = [];
    const referenceColumnNames = referenceRow.columns.map((c) => c.name);
    const referenceColumnTypes = new Map(referenceRow.columns.map((c) => [c.name, c.type]));

    for (const row of taggedRowsWithCounts) {
      if (row.id === referenceRow.id) continue;
      if (!row.columns || row.columns.length === 0) continue; // Still analyzing

      // 1. Column count check
      if (row.colCount !== referenceRow.colCount) {
        errors.push({
          type: 'column_count',
          message: `Column count mismatch. ${referenceRow.file.name} has ${referenceRow.colCount} columns, ${row.file.name} has ${row.colCount} columns.`,
          details: {
            file1: referenceRow.file.name,
            file2: row.file.name,
            count1: referenceRow.colCount,
            count2: row.colCount,
          },
        });
      }

      // 2. Column name check (case-sensitive)
      const rowColumnNames = row.columns.map((c) => c.name);
      const missingColumns = referenceColumnNames.filter((name) => !rowColumnNames.includes(name));
      const extraColumns = rowColumnNames.filter((name) => !referenceColumnNames.includes(name));
      const commonColumns = referenceColumnNames.filter((name) => rowColumnNames.includes(name));

      if (missingColumns.length > 0 || extraColumns.length > 0) {
        errors.push({
          type: 'column_name',
          message: `Column name mismatch detected between ${referenceRow.file.name} and ${row.file.name}.`,
          details: {
            file1: referenceRow.file.name,
            file2: row.file.name,
            missingColumns,
            extraColumns,
            commonColumns,
          },
        });
      }

      // 3. Data type consistency check (only for common columns)
      const typeMismatches: Array<{
        column: string;
        type1: string;
        type2: string;
        file1: string;
        file2: string;
      }> = [];

      for (const col of row.columns) {
        const refType = referenceColumnTypes.get(col.name);
        if (refType && refType !== col.type) {
          typeMismatches.push({
            column: col.name,
            type1: refType,
            type2: col.type,
            file1: referenceRow.file.name,
            file2: row.file.name,
          });
        }
      }

      if (typeMismatches.length > 0) {
        errors.push({
          type: 'data_type',
          message: `Data type mismatch detected between ${referenceRow.file.name} and ${row.file.name}.`,
          details: {
            file1: referenceRow.file.name,
            file2: row.file.name,
            typeMismatches,
          },
        });
      }
    }

    return { isValid: errors.length === 0, errors };
  }, [workflowPath, taggedRowsWithCounts]);

  const schemaMatch = schemaValidation.isValid;

  // Split/dataset confirmation handler
  const handleConfirmSplit = async () => {
    // Step 1: Validate
    setSplitConfirmationState((prev) => ({
      ...prev,
      isConfirming: true,
      currentStep: 1,
      error: null,
    }));

    try {
      if (!effectiveTargetVar) {
        throw new Error('Please select a target variable before confirming.');
      }
      if (!hasValidTargetVariableType) {
        throw new Error('Please select a variable category (Numerical or Categorical).');
      }
      if (uniqueIdsForObjectives.length === 0) {
        throw new Error('Please select at least one Unique ID variable.');
      }

      const datasetConfigRaw = sessionStorage.getItem('dataset_config');
      const dsConfig = datasetConfigRaw ? JSON.parse(datasetConfigRaw) : {};

      let trainRows = 0;
      let testRows = 0;
      let validationRows = 0;

      if (workflowPath === 'platform_split') {
        // Platform split: validate ratios and compute from total rows
        const splitConfig = dsConfig?.split_configuration;

        if (!splitConfig) {
          throw new Error('Split configuration not found. Please configure the data partition first.');
        }

        const ratios = splitConfig.ratios || { train: 70, test: 15, validation: 15 };
        const totalRatio = ratios.train + ratios.test + ratios.validation;

        if (Math.abs(totalRatio - 100) > 0.01) {
          throw new Error(`Split ratios must sum to 100%. Current sum: ${totalRatio}%`);
        }

        // Step 2: Execute split
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 2 }));
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Step 3: Compute stats
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 3 }));
        const totalRows = datasetAnalysis?.totalRows || 0;
        trainRows = Math.round(totalRows * ratios.train / 100);
        testRows = Math.round(totalRows * ratios.test / 100);
        validationRows = totalRows - trainRows - testRows;
        await new Promise((resolve) => setTimeout(resolve, 400));

        // Step 4: Store partitions
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 4 }));
        await new Promise((resolve) => setTimeout(resolve, 400));

        // Step 5: Store metadata
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 5 }));
        const fullSplitConfig = {
          ...splitConfig,
          confirmed: true,
          confirmed_at: new Date().toISOString(),
          target_variable: effectiveTargetVar,
          partition_stats: {
            train: { rows: trainRows, percentage: ratios.train },
            test: { rows: testRows, percentage: ratios.test },
            validation: { rows: validationRows, percentage: ratios.validation },
          },
        };
        const updatedDsConfig = { ...dsConfig, split_configuration: fullSplitConfig };
        sessionStorage.setItem('dataset_config', JSON.stringify(updatedDsConfig));
        await new Promise((resolve) => setTimeout(resolve, 300));

      } else if (workflowPath === 'pre_split') {
        // Pre-split: validate uploaded partitions
        if (validationErrors.length > 0) {
          throw new Error(`Validation errors: ${validationErrors.join(', ')}`);
        }

        const hasTrain = selectedDataSources.some((s: any) => s?.type === 'file' && s.partitionRole === 'train');
        if (!hasTrain) {
          throw new Error('Train partition is required.');
        }

        if (taggedRowsWithCounts.length > 1 && !schemaMatch) {
          const errorTypes = schemaValidation.errors.map((e) => e.type);
          const uniqueTypes = [...new Set(errorTypes)];
          const typeLabels = uniqueTypes.map((t) => {
            if (t === 'column_count') return 'column count mismatch';
            if (t === 'column_name') return 'column name mismatch';
            if (t === 'data_type') return 'data type mismatch';
            return t;
          });
          throw new Error(`Schema validation failed: ${typeLabels.join(', ')}. See details above.`);
        }

        // Step 2: Accept partitions
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 2 }));
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Step 3: Compute stats from uploaded files (with exclusion rules applied)
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 3 }));
        const trainData = taggedRowsWithCounts.find((r) => r.role === 'train');
        const testData = taggedRowsWithCounts.find((r) => r.role === 'test');
        const validationData = taggedRowsWithCounts.find((r) => r.role === 'oot');
        
        // Get adjusted row counts after exclusion rules
        const exclusionRules = dsConfig.exclusion_rules;
        const variablesToRemove = dsConfig.variables_to_remove;
        
        // Helper to get adjusted row count for a partition
        const getAdjustedRowCount = async (partitionData: typeof trainData, file: File | undefined) => {
          if (!partitionData) return 0;
          let rowCount = partitionData.rowCount || 0;
          
          // Apply exclusion rules if any
          if (file && exclusionRules && Array.isArray(exclusionRules) && exclusionRules.length > 0 && effectiveTargetVar) {
            try {
              const result = await fastApiService.getExclusionPreview(file, exclusionRules, effectiveTargetVar);
              if (result.waterfall && result.waterfall.length > 0) {
                const lastStep = result.waterfall[result.waterfall.length - 1];
                rowCount = lastStep.remaining;
              }
            } catch (e) {
              console.error('Failed to get exclusion preview for partition:', e);
            }
          }
          
          return rowCount;
        };
        
        // Get files for each partition
        const trainFile = selectedDataSources.find((s: any) => s?.type === 'file' && s.partitionRole === 'train')?.file as File | undefined;
        const testFile = selectedDataSources.find((s: any) => s?.type === 'file' && s.partitionRole === 'test')?.file as File | undefined;
        
        // Handle multiple validation files
        const validationFiles = selectedDataSources
          .filter((s: any) => s?.type === 'file' && s.partitionRole === 'oot')
          .map((s: any) => s.file as File);
        
        // Compute adjusted row counts
        trainRows = await getAdjustedRowCount(trainData, trainFile);
        testRows = await getAdjustedRowCount(testData, testFile);
        
        // Sum up validation rows from all validation files
        if (validationFiles.length > 0) {
          let totalValidationRows = 0;
          for (const valFile of validationFiles) {
            const valData = taggedRowsWithCounts.find((r: any) => r.file?.name === valFile.name);
            const valRows = await getAdjustedRowCount(valData, valFile);
            totalValidationRows += valRows;
          }
          validationRows = totalValidationRows;
        } else {
          validationRows = await getAdjustedRowCount(validationData, undefined);
        }
        
        await new Promise((resolve) => setTimeout(resolve, 200));

        // Step 4: Register partitions
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 4 }));
        await new Promise((resolve) => setTimeout(resolve, 400));

        // Step 5: Store metadata
        setSplitConfirmationState((prev) => ({ ...prev, currentStep: 5 }));
        const totalRows = trainRows + testRows + validationRows;
        const preSplitConfig = {
          ingestion_mode: 'pre_split',
          confirmed: true,
          confirmed_at: new Date().toISOString(),
          target_variable: effectiveTargetVar,
          partition_stats: {
            train: { rows: trainRows, percentage: totalRows > 0 ? Math.round(trainRows / totalRows * 100) : 0 },
            test: { rows: testRows, percentage: totalRows > 0 ? Math.round(testRows / totalRows * 100) : 0 },
            validation: { rows: validationRows, percentage: totalRows > 0 ? Math.round(validationRows / totalRows * 100) : 0 },
          },
        };
        const updatedDsConfig = { ...dsConfig, split_configuration: preSplitConfig };
        sessionStorage.setItem('dataset_config', JSON.stringify(updatedDsConfig));
        await new Promise((resolve) => setTimeout(resolve, 300));
      }

      // NOTE: Scope is set to train on Submit button click (in handleSubmitDataset)
      // This ensures the transition happens at the right time for both pre-split and platform split

      // Step 6: Show confirmation
      setSplitConfirmationState((prev) => ({
        ...prev,
        currentStep: 6,
        isConfirming: false,
        isConfirmed: true,
        stats: {
          trainRows,
          testRows,
          validationRows,
          trainEventRate: null,
          testEventRate: null,
          validationEventRate: null,
        },
      }));
    } catch (err: any) {
      setSplitConfirmationState((prev) => ({
        ...prev,
        isConfirming: false,
        error: err.message || 'Failed to confirm',
        currentStep: 0,
      }));
    }
  };

  // Check if split/datasets can be confirmed
  const canConfirmSplit = useMemo(() => {
    if (!datasetAnalysis) return false;
    if (!effectiveTargetVar) return false;
    if (!hasValidTargetVariableType) return false;
    if (uniqueIdsForObjectives.length === 0) return false;

    // For platform_split: check split configuration ratios
    if (workflowPath === 'platform_split') {
      const datasetConfigRaw = sessionStorage.getItem('dataset_config');
      if (!datasetConfigRaw) return false;

      try {
        const dsConfig = JSON.parse(datasetConfigRaw);
        const splitConfig = dsConfig.split_configuration;
        if (!splitConfig) return false;
        
        const ratios = splitConfig.ratios || {};
        const total = (ratios.train || 0) + (ratios.test || 0) + (ratios.validation || 0);
        return Math.abs(total - 100) < 0.01;
      } catch {
        return false;
      }
    }

    // For pre_split: check validation passed and has required partitions
    if (workflowPath === 'pre_split') {
      // Must have no validation errors
      if (validationErrors.length > 0) return false;
      // Must have at least train partition
      const hasTrain = selectedDataSources.some((s: any) => s?.type === 'file' && s.partitionRole === 'train');
      if (!hasTrain) return false;
      // Schema must match if multiple files
      if (taggedRowsWithCounts.length > 1 && !schemaMatch) return false;
      return true;
    }

    return false;
  }, [
    workflowPath,
    datasetAnalysis,
    effectiveTargetVar,
    hasValidTargetVariableType,
    uniqueIdsForObjectives,
    validationErrors,
    selectedDataSources,
    taggedRowsWithCounts,
    schemaMatch,
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Data ingestion</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Define objectives and add data for model training.</p>
        </div>
      </div>

      <div className="flex items-center space-x-3 text-sm">
        {activeDatasetId && (
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
              <span>Active Dataset:&nbsp;{activeDatasetId}</span>
              <button
                className="ml-1 text-blue-500 hover:text-blue-700"
                onClick={() => {
                  sessionStorage.removeItem('dataset_id');
                  sessionStorage.removeItem('dataset_config');
                  setActiveDatasetId(null);
                  setDatasetConfig(null);
                  setShowDatasetOverview(false);
                }}
              >
                ×
              </button>
            </span>
            <button
              onClick={() => setShowDatasetOverview(true)}
              className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors"
            >
              <Eye className="h-3 w-3" />
              <span>View Dataset</span>
            </button>
          </div>
        )}
      </div>

      {!activeDatasetId && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">Upload your data</p>

          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 md:p-5">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">Local File Upload</h3>
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors bg-white dark:bg-gray-800 ${
                    dragActive ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  <Upload className="h-10 w-10 text-gray-400 dark:text-gray-500 mx-auto mb-3" />
                  <p className="text-gray-600 dark:text-gray-400 mb-1">
                    Drop CSV files here, or{' '}
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="text-blue-600 hover:text-blue-700 font-medium underline"
                    >
                      click to browse
                    </button>
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">You can upload one or more files · CSV only</p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".csv"
                  onChange={handleFileInput}
                />
              </div>

              <div className="space-y-4">
                {/* Show grid only when no integration is selected */}
                {!selectedIntegration ? (
                  <>
                    <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">Database &amp; Cloud Integrations</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Connectors below are not available yet. Use local file upload to add data.
                    </p>
                    <div className="grid grid-cols-2 gap-3 overflow-y-auto pr-1" style={{ maxHeight: '260px' }}>
                      {INTEGRATION_DATA_SOURCES.map((source) => (
                        <button
                          key={source.id}
                          type="button"
                          disabled={DISABLE_DATABASE_CLOUD_INTEGRATIONS}
                          onClick={() => handleIntegrationSelect(source)}
                          className="p-3 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition text-left h-14 flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-gray-800"
                        >
                          <span className="text-lg">{source.icon}</span>
                          <span className="text-sm font-medium truncate text-gray-800 dark:text-gray-200">
                            {source.name}
                          </span>
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  /* Show ONLY the configuration form when integration is selected */
                  <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-blue-200 dark:border-blue-700">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                        Configure {selectedIntegration.name}
                      </h4>
                      <button
                        type="button"
                        onClick={handleIntegrationCancel}
                        className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition"
                      >
                        <X className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                      </button>
                    </div>
                    
                    {selectedIntegration.type === 'database' ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Host</label>
                            <input
                              type="text"
                              value={integrationConfigData.host || ''}
                              onChange={(e) => handleIntegrationConfigChange('host', e.target.value)}
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="localhost"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Port</label>
                            <input
                              type="text"
                              value={integrationConfigData.port || ''}
                              onChange={(e) => handleIntegrationConfigChange('port', e.target.value)}
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="5432"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Database</label>
                          <input
                            type="text"
                            value={integrationConfigData.database || ''}
                            onChange={(e) => handleIntegrationConfigChange('database', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="mydatabase"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
                            <input
                              type="text"
                              value={integrationConfigData.username || ''}
                              onChange={(e) => handleIntegrationConfigChange('username', e.target.value)}
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              placeholder="username"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
                            <div className="relative">
                              <input
                                type={showIntegrationPassword ? 'text' : 'password'}
                                value={integrationConfigData.password || ''}
                                onChange={(e) => handleIntegrationConfigChange('password', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-8"
                                placeholder="password"
                              />
                              <button
                                type="button"
                                onClick={() => setShowIntegrationPassword(!showIntegrationPassword)}
                                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
                              >
                                {showIntegrationPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : selectedIntegration.id === 'google-sheets' ? (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Spreadsheet ID</label>
                          <input
                            type="text"
                            value={integrationConfigData.spreadsheetId || ''}
                            onChange={(e) => handleIntegrationConfigChange('spreadsheetId', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Sheet Name</label>
                          <input
                            type="text"
                            value={integrationConfigData.sheetName || ''}
                            onChange={(e) => handleIntegrationConfigChange('sheetName', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="Sheet1"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
                          <input
                            type="password"
                            value={integrationConfigData.apiKey || ''}
                            onChange={(e) => handleIntegrationConfigChange('apiKey', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="AIzaSy..."
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Connection String</label>
                          <input
                            type="text"
                            value={integrationConfigData.connectionString || ''}
                            onChange={(e) => handleIntegrationConfigChange('connectionString', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="Enter connection string..."
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
                          <input
                            type="password"
                            value={integrationConfigData.apiKey || ''}
                            onChange={(e) => handleIntegrationConfigChange('apiKey', e.target.value)}
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="Enter API key..."
                          />
                        </div>
                      </div>
                    )}
                    
                    {integrationValidationErrors.length > 0 && (
                      <div className="mt-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-2">
                        <ul className="list-disc list-inside text-xs text-red-700 dark:text-red-300 space-y-0.5">
                          {integrationValidationErrors.map((error, index) => (
                            <li key={index}>{error}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    <div className="flex space-x-2 mt-4 pt-3 border-t border-gray-200 dark:border-gray-600">
                      <button
                        type="button"
                        onClick={handleIntegrationCancel}
                        className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleIntegrationConnect}
                        className="px-3 py-1.5 text-sm bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition font-medium"
                      >
                        Connect
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {uploadedRows.length > 0 && (
            <div className="mt-6 space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                After each file appears, choose its partition tag.
              </p>
              {uploadedRows.map((row) => {
                const role = row.role;
                return (
                  <div
                    key={row.id}
                    className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
                  >
                    <span className="font-medium text-gray-900 dark:text-gray-100 truncate min-w-0 pr-2">{row.file.name}</span>
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 flex-shrink-0 w-full sm:w-auto">
                      {!role ? (
                        <div className="flex flex-wrap gap-2">
                          {(['full', 'train', 'test', 'oot'] as PartitionRole[]).map((r) => {
                            const disabled = usedRoles.has(r);
                            return (
                              <button
                                key={r}
                                type="button"
                                disabled={disabled}
                                onClick={() => handleAssignTagForRow(row.id, r)}
                                title={
                                  disabled
                                    ? (r === 'oot' ? 'Maximum 3 validation datasets allowed.' : 'Only one dataset allowed for this tag.')
                                    : `Tag as ${PILL_LABELS[r]}`
                                }
                                className={`px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium border transition-colors ${
                                  disabled
                                    ? 'bg-gray-50 dark:bg-gray-700/50 text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-600 cursor-not-allowed'
                                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                                }`}
                              >
                                {PILL_LABELS[r]}
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <span
                          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium border w-fit ${ROLE_COLORS[role].bg} ${ROLE_COLORS[role].text} ${ROLE_COLORS[role].border}`}
                        >
                          {ROW_BADGE_LABELS[role]}
                        </span>
                      )}
                      <div className="flex items-center gap-3 sm:ml-auto">
                        {row.uploadProgress !== undefined && row.uploadProgress < 100 && !row.uploadError && (
                          <div className="flex items-center gap-2" title="Uploading to server">
                            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                            <span className="text-sm text-blue-600 dark:text-blue-400 tabular-nums font-medium">
                              {Math.round(row.uploadProgress)}%
                            </span>
                          </div>
                        )}
                        {row.uploadError && (
                          <span className="text-sm text-red-500 dark:text-red-400 font-medium">Upload failed</span>
                        )}
                        <span className="text-sm text-gray-500 dark:text-gray-400 tabular-nums whitespace-nowrap">
                          {row.isAnalyzing
                            ? 'Analyzing…'
                            : row.rowCount != null
                              ? `${row.rowCount.toLocaleString()} rows · ${row.colCount} cols`
                              : ''}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveRow(row.id)}
                          className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                          aria-label="Remove file"
                        >
                          <X className="h-5 w-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}

              {workflowPath === 'pre_split' &&
                !(usedRoles.has('train') && usedRoles.has('test') && usedRoles.has('oot')) && (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 font-medium border border-dashed border-blue-300 rounded-lg px-4 py-2"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Upload another dataset
                  </button>
                )}
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                {validationErrors.map((err, i) => (
                  <p key={i} className="text-sm text-red-700 dark:text-red-300">
                    {err}
                  </p>
                ))}
              </div>
            </div>
          )}

          {workflowPath === 'platform_split' && validationErrors.length === 0 && !hasUntaggedFiles && fileCount > 0 && (
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg flex items-start gap-2">
              <Settings className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">Platform will split your data</p>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  Since you uploaded a full dataset, you&apos;ll configure train / test / validation ratios and split method in
                  the next step.
                </p>
              </div>
            </div>
          )}

          {workflowPath === 'pre_split' && validationErrors.length === 0 && !hasUntaggedFiles && fileCount > 0 && (
            <div className="mt-4 space-y-3">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-green-800 dark:text-green-200">Using your pre-split datasets</p>
                  <p className="text-sm text-green-700 dark:text-green-300">
                    Schema and target validation will run automatically. You&apos;ll review partition statistics before
                    proceeding.
                  </p>
                </div>
              </div>
              {/* Schema Validation Results */}
              {taggedRowsWithCounts.length > 1 && (
                <>
                  {schemaMatch && taggedRowsWithCounts[0] && (
                    <div className="px-4 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                      <p className="text-sm text-green-700 dark:text-green-300">
                        <CheckCircle className="inline h-4 w-4 mr-1 align-text-bottom" />
                        Schema validated - {taggedRowsWithCounts[0].colCount} columns, names and types consistent across all datasets
                      </p>
                    </div>
                  )}
                  {!schemaMatch && schemaValidation.errors.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-semibold text-red-700 dark:text-red-300 mb-2">
                        Schema validation failed - resolve the following issues to proceed:
                      </p>
                      <SchemaValidationErrors errors={schemaValidation.errors} />
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Problem Statement and Data Dictionary */}
          <div className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Problem Statement (Optional)</label>
              <textarea
                rows={3}
                value={
                  datasetConfig?.problem_statement ||
                  (chatInputs['problem_stmt' as unknown as number] as unknown as string) ||
                  ''
                }
                onChange={(e) => {
                  const newValue = e.target.value;
                  setChatInputs((prev: any) => ({ ...prev, ['problem_stmt' as unknown as number]: newValue }));
                  if (datasetConfig) {
                    setDatasetConfig((prev: any) => (prev ? { ...prev, problem_statement: newValue } : null));
                    sessionStorage.setItem('dataset_config', JSON.stringify({ ...datasetConfig, problem_statement: newValue }));
                  }
                  updateModelObjective({ problemStatement: newValue });
                }}
                placeholder="Describe the business problem you're trying to solve..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Data Dictionary (Optional)</label>
              {!dataDictionaryFile ? (
                <div className="relative">
                  <input
                    id="data-dictionary-upload"
                    type="file"
                    accept=".csv"
                    onChange={onDataDictionaryFileSelect}
                    className="hidden"
                  />
                  <label
                    htmlFor="data-dictionary-upload"
                    className="w-full px-3 py-2 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:border-blue-400 transition-colors flex items-center justify-center bg-gray-50 dark:bg-gray-700/50 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                  >
                    <div className="text-center">
                      <Upload className="h-5 w-5 text-gray-400 dark:text-gray-500 mx-auto mb-1" />
                      <span className="text-sm text-gray-600 dark:text-gray-400">Upload CSV file with column descriptions</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400 block mt-1">Click to browse or drag and drop</span>
                    </div>
                  </label>
                </div>
              ) : (
                <div className="flex items-center justify-between p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-green-50 dark:bg-green-900/20">
                  <div className="flex items-center space-x-2">
                    <FileText className="h-4 w-4 text-green-600 dark:text-green-400" />
                    <span className="text-sm font-medium text-green-800 dark:text-green-200">{dataDictionaryFile.name}</span>
                    <span className="text-xs text-green-600 dark:text-green-300">({formatFileSize(dataDictionaryFile.size)})</span>
                  </div>
                  <button
                    type="button"
                    onClick={onRemoveDataDictionaryFile}
                    className="p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded text-red-500 hover:text-red-700 transition-colors"
                    title="Remove file"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Proceed Button - Required to continue to Dataset Configuration */}
          {!hasProceededToConfig && selectedDataSources.length > 0 && !activeDatasetId && (
            <div className="mt-6 flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {workflowPath === 'pre_split' 
                  ? 'Files will be combined into a single dataset with partition tags.'
                  : 'Click to proceed with dataset configuration.'}
              </p>
              <button
                type="button"
                onClick={onProceedToConfig}
                disabled={
                  isProceedingToConfig ||
                  validationErrors.length > 0 ||
                  hasUntaggedFiles ||
                  proceedToConfigBlockedByRowPipeline
                }
                title={
                  proceedToConfigBlockedByRowPipeline
                    ? 'Wait for upload and dataset analysis to finish (100% and row/column counts) for all files.'
                    : undefined
                }
                className="px-6 py-2.5 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2 font-medium"
              >
                {isProceedingToConfig ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    <span>{workflowPath === 'pre_split' ? 'Combining files…' : 'Processing…'}</span>
                  </>
                ) : (
                  <>
                    <span>Proceed to Configuration</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {(hasProceededToConfig || activeDatasetId) && (selectedDataSources.length > 0 || activeDatasetId) && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Dataset Configuration</h3>
            {isAnalyzingDataset && (
              <div className="flex items-center space-x-2 text-sm text-blue-600 dark:text-blue-400">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 dark:border-blue-400" />
                <span>Analyzing dataset…</span>
              </div>
            )}
          </div>

          <div className="pt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Target Variable <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              {datasetAnalysis ? (
                <>
                  <select
                    value={
                      datasetConfig?.target_variable ||
                      (chatInputs['target_var' as unknown as number] as unknown as string) ||
                      ''
                    }
                    disabled={objectivesFormLocked}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      setChatInputs((prev: any) => ({ ...prev, ['target_var' as unknown as number]: newValue }));
                      if (datasetConfig) {
                        setDatasetConfig((prev: any) => (prev ? { ...prev, target_variable: newValue } : null));
                        sessionStorage.setItem('dataset_config', JSON.stringify({ ...datasetConfig, target_variable: newValue }));
                      }
                      const selectedColumn = datasetAnalysis.columns.find((col: any) => col.name === newValue);
                      if (selectedColumn) {
                        const cat = mapColumnToVariableCategory(selectedColumn);
                        setChatInputs((prev: any) => ({ ...prev, ['target_type' as unknown as number]: cat }));
                        if (datasetConfig) {
                          setDatasetConfig((prev: any) => (prev ? { ...prev, target_variable_type: cat } : null));
                          sessionStorage.setItem(
                            'dataset_config',
                            JSON.stringify({ ...datasetConfig, target_variable: newValue, target_variable_type: cat })
                          );
                        }
                      } else if (!newValue) {
                        setChatInputs((prev: any) => ({ ...prev, ['target_type' as unknown as number]: '' }));
                        if (datasetConfig) {
                          const cleared = { ...datasetConfig, target_variable: '', target_variable_type: '' as unknown as 'Numerical' | 'Categorical' };
                          setDatasetConfig(cleared);
                          sessionStorage.setItem('dataset_config', JSON.stringify(cleared));
                        }
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    <option value="">Select a target variable</option>
                    {datasetAnalysis.columns.map((column: any) => (
                      <option key={column.name} value={column.name}>
                        {column.name} ({getDisplayType(column)})
                      </option>
                    ))}
                  </select>
                  {!effectiveTargetVar && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">Please select a target variable</p>
                  )}
                </>
              ) : (
                <input
                  type="text"
                  disabled={objectivesFormLocked}
                  value={
                    datasetConfig?.target_variable ||
                    (chatInputs['target_var' as unknown as number] as unknown as string) ||
                    ''
                  }
                  onChange={(e) => {
                    const newValue = e.target.value;
                    setChatInputs((prev: any) => ({ ...prev, ['target_var' as unknown as number]: newValue }));
                    if (datasetConfig) {
                      setDatasetConfig((prev: any) => (prev ? { ...prev, target_variable: newValue } : null));
                      sessionStorage.setItem('dataset_config', JSON.stringify({ ...datasetConfig, target_variable: newValue }));
                    }
                  }}
                  placeholder="Upload a dataset to see available columns"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
                />
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Variable category <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              <select
                value={
                  (datasetConfig?.target_variable_type ||
                    (chatInputs['target_type' as unknown as number] as unknown as string) ||
                    '') as string
                }
                disabled={objectivesFormLocked}
                onChange={(e) => {
                  const raw = e.target.value;
                  setChatInputs((prev: any) => ({ ...prev, ['target_type' as unknown as number]: raw }));
                  if (datasetConfig) {
                    setDatasetConfig((prev: any) =>
                      prev ? { ...prev, target_variable_type: raw } : null
                    );
                    sessionStorage.setItem(
                      'dataset_config',
                      JSON.stringify({ ...datasetConfig, target_variable_type: raw })
                    );
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <option value="">Select variable category</option>
                <option value="Categorical">Categorical</option>
                <option value="Numerical">Numerical</option>
              </select>
              {datasetAnalysis && !!effectiveTargetVar && !hasValidTargetVariableType && (
                <p className="mt-2 text-sm text-red-600 dark:text-red-400">Please select a variable category</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Unique ID / Combinations <span className="text-red-500 dark:text-red-400">*</span>
              </label>
              {datasetAnalysis ? (
                <>
                  <CheckboxMultiselect
                    options={datasetAnalysis.columns}
                    selectedValues={datasetConfig?.unique_id_combinations || []}
                    disabled={objectivesFormLocked}
                    onChange={(selectedOptions) => {
                      setChatInputs((prev: any) => ({
                        ...prev,
                        ['unique_id_combinations' as unknown as number]: selectedOptions,
                      }));
                      const updatedConfig = datasetConfig
                        ? { ...datasetConfig, unique_id_combinations: selectedOptions }
                        : {
                            target_variable: '',
                            target_variable_type: '' as unknown as 'Numerical' | 'Categorical',
                            dataset_structure_type: 'others' as const,
                            problem_statement: '',
                            data_dictionary: '',
                            unique_id_combinations: selectedOptions,
                            segmentation_variable: '',
                            weight_variable: '',
                            sample_identifier_variable: '',
                          };
                      setDatasetConfig(updatedConfig);
                      sessionStorage.setItem('dataset_config', JSON.stringify(updatedConfig));
                      validateUniqueIds(selectedOptions);
                    }}
                    placeholder="Select unique ID variables"
                  />
                  {(!datasetConfig?.unique_id_combinations || datasetConfig.unique_id_combinations.length === 0) && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">Please select at least one unique ID variable</p>
                  )}
                  {isValidatingUniqueIds && <p className="mt-2 text-sm text-blue-600 dark:text-blue-400">Validating unique IDs…</p>}
                  {uniqueIdWarning && (
                    <div className="mt-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg">
                      <p className="text-sm text-yellow-800 dark:text-yellow-200">{uniqueIdWarning}</p>
                    </div>
                  )}
                </>
              ) : (
                <input
                  type="text"
                  value=""
                  placeholder="Upload a dataset to see available columns"
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 dark:text-gray-400 cursor-not-allowed"
                />
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Segmentation Variable (Optional)</label>
              {datasetAnalysis ? (
                <select
                  value={
                    datasetConfig?.segmentation_variable ||
                    (chatInputs['segmentation_variable' as unknown as number] as unknown as string) ||
                    ''
                  }
                  disabled={objectivesFormLocked}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    setChatInputs((prev: any) => ({ ...prev, ['segmentation_variable' as unknown as number]: newValue }));
                    if (datasetConfig) {
                      setDatasetConfig((prev: any) => (prev ? { ...prev, segmentation_variable: newValue } : null));
                      sessionStorage.setItem(
                        'dataset_config',
                        JSON.stringify({ ...datasetConfig, segmentation_variable: newValue })
                      );
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="">Select a segmentation variable</option>
                  {datasetAnalysis.columns.map((column: any) => (
                    <option key={column.name} value={column.name}>
                      {column.name} ({getDisplayType(column)})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value=""
                  placeholder="Upload a dataset to see available columns"
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 dark:text-gray-400 cursor-not-allowed"
                />
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Weight Variable (Optional)</label>
              {datasetAnalysis ? (
                <select
                  value={datasetConfig?.weight_variable || ''}
                  disabled={objectivesFormLocked}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    if (datasetConfig) {
                      setDatasetConfig((prev: any) => (prev ? { ...prev, weight_variable: newValue } : null));
                      sessionStorage.setItem(
                        'dataset_config',
                        JSON.stringify({ ...datasetConfig, weight_variable: newValue })
                      );
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="">No weight variable</option>
                  {datasetAnalysis.columns
                    .filter((column: any) => {
                      if (column.name === effectiveTargetVar) return false;
                      const storedConfig = sessionStorage.getItem('dataset_config');
                      if (storedConfig) {
                        try {
                          const cfg = JSON.parse(storedConfig);
                          const sc = cfg.split_configuration;
                          if (sc?.split_method === 'user_identifier' && column.name === sc.identifier_column) {
                            return false;
                          }
                        } catch {
                          // ignore parse errors
                        }
                      }
                      return true;
                    })
                    .map((column: any) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                </select>
              ) : (
                <div className="text-gray-500 dark:text-gray-400 text-sm">Loading columns...</div>
              )}
            </div>
          </div>

          {/* Additional Dataset Configuration */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {datasetAnalysis && effectiveTargetVar && (
              <ExclusionRulesPanel
                datasetAnalysis={datasetAnalysis}
                selectedDataSources={selectedDataSources}
                targetVariable={effectiveTargetVar}
                originalRowCount={originalRowCount}
                onExclusionRulesChange={(groups) => {
                  setExclusionRules(groups);
                  // Store in sessionStorage for downstream use
                  try {
                    const cfg = sessionStorage.getItem('dataset_config');
                    const parsed = cfg ? JSON.parse(cfg) : {};
                    parsed.exclusion_rules = groups;
                    sessionStorage.setItem('dataset_config', JSON.stringify(parsed));
                    // Dispatch event to trigger ReviewStatsPanel refresh
                    window.dispatchEvent(new CustomEvent('datasetConfigChanged'));
                  } catch (e) {
                    console.error('Failed to save exclusion rules:', e);
                  }
                }}
                onFilteredRowsChange={handleFilteredRowsChange}
              />
            )}

            {/* Variable Review Section */}
            {datasetAnalysis && effectiveTargetVar && selectedDataSources[0]?.file && (
              <div className="md:col-span-2 lg:col-span-3 space-y-4">
                <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Variable review</p>
                
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                  {!showVariableReview && !variableReviewCompleted && (
                    <button
                      type="button"
                      onClick={() => setShowVariableReview(true)}
                      disabled={objectivesFormLocked}
                      title={
                        objectivesFormLocked
                          ? 'Partition is confirmed; variable review cannot be changed for this project.'
                          : undefined
                      }
                      className="px-3 py-1.5 text-xs font-medium text-white bg-orange-500 rounded-md hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-orange-500"
                    >
                      Run Review
                    </button>
                  )}
                
                {showVariableReview && (
                  <VariableReviewPanel
                    file={selectedDataSources[0]?.file}
                    targetVariable={effectiveTargetVar}
                    sampleIdVariable={datasetConfig?.sample_identifier_variable || null}
                    weightVariable={datasetConfig?.weight_variable || null}
                    dataDictionaryFile={dataDictionaryFile}
                    onApply={(removed) => {
                      setRemovedVariables(removed);
                      setVariableReviewCompleted(true);
                      setShowVariableReview(false);
                      
                      // Update datasetAnalysis to exclude removed columns
                      // This ensures Data Partitioning, Review Stats, and other downstream
                      // components see the filtered column list
                      if (datasetAnalysis && setDatasetAnalysis && removed.length > 0) {
                        const filteredColumns = datasetAnalysis.columns.filter(
                          (col: any) => !removed.includes(col.name)
                        );
                        setDatasetAnalysis({
                          ...datasetAnalysis,
                          columns: filteredColumns,
                          totalColumns: filteredColumns.length,
                        });
                        console.log(`[Variable Review] Removed ${removed.length} variables. ` +
                          `Columns: ${datasetAnalysis.totalColumns} → ${filteredColumns.length}`);
                      }
                      
                      // Store removed variables in sessionStorage for upload
                      try {
                        const cfg = sessionStorage.getItem('dataset_config');
                        const parsed = cfg ? JSON.parse(cfg) : {};
                        parsed.variables_to_remove = removed;
                        sessionStorage.setItem('dataset_config', JSON.stringify(parsed));
                        // Dispatch event to trigger ReviewStatsPanel refresh
                        window.dispatchEvent(new CustomEvent('datasetConfigChanged'));
                      } catch (e) {
                        console.error('Failed to save removed variables:', e);
                      }
                    }}
                    onProceedWithoutRemoving={() => {
                      setVariableReviewCompleted(true);
                      setShowVariableReview(false);
                    }}
                  />
                )}
                
                {variableReviewCompleted && !showVariableReview && (
                  <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                        <p className="text-sm font-medium text-green-800 dark:text-green-200">
                          Variable review completed
                          {removedVariables.length > 0 && (
                            <span className="ml-1 text-green-600 dark:text-green-300">
                              ({removedVariables.length} variable{removedVariables.length !== 1 ? 's' : ''} removed)
                            </span>
                          )}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setShowVariableReview(true);
                          setVariableReviewCompleted(false);
                        }}
                        disabled={objectivesFormLocked}
                        title={
                          objectivesFormLocked
                            ? 'Partition is confirmed; variable review cannot be changed for this project.'
                            : undefined
                        }
                        className="text-sm text-green-700 dark:text-green-300 hover:text-green-800 dark:hover:text-green-200 underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
                      >
                        Re-run review
                      </button>
                    </div>
                  </div>
                )}
                </div>
              </div>
            )}

            {workflowPath === 'platform_split' && datasetAnalysis && (
              <div className="md:col-span-2 lg:col-span-3 space-y-2">
                <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Data partitioning</p>
                <PlatformPartitionSection
                  datasetAnalysis={datasetAnalysis}
                  activeDatasetId={activeDatasetId}
                  selectedDataSources={selectedDataSources}
                  targetVariable={effectiveTargetVar}
                  getDisplayType={getDisplayType}
                  controlsDisabled={!hasRequiredObjectiveFields || objectivesFormLocked}
                />
              </div>
            )}

            {(workflowPath === 'pre_split' || (workflowPath === 'platform_split' && datasetAnalysis)) && (
              <ReviewStatsPanel
                workflowPath={workflowPath}
                datasetAnalysis={datasetAnalysis}
                selectedDataSources={selectedDataSources}
                targetVariable={effectiveTargetVar}
                uploadedRows={uploadedRows}
                schemaMatch={schemaMatch}
                activeDatasetId={activeDatasetId}
                pendingDatasetId={pendingDatasetId ?? uploadedRows.find(r => r.role === 'full' || !r.role)?.uploadedDatasetId ?? null}
              />
            )}

            {datasetAnalysis && (
              <div className="md:col-span-2 lg:col-span-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h5 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Dataset Analysis</h5>
                {(() => {
                  const numericalCount = datasetAnalysis.columns.filter((col: any) => getDisplayType(col) === 'Numerical').length;
                  const categoricalCount = datasetAnalysis.columns.filter((col: any) => getDisplayType(col) === 'Categorical')
                    .length;
                  const dateCount = datasetAnalysis.columns.filter((col: any) => getDisplayType(col) === 'Date').length;
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-blue-700 dark:text-blue-300">Total Rows:</span>
                        <span className="ml-1 font-medium dark:text-blue-100">{datasetAnalysis.totalRows.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-blue-700 dark:text-blue-300">Total Columns:</span>
                        <span className="ml-1 font-medium dark:text-blue-100">{datasetAnalysis.totalColumns}</span>
                      </div>
                      <div>
                        <span className="text-blue-700 dark:text-blue-300">Numerical:</span>
                        <span className="ml-1 font-medium dark:text-blue-100">{numericalCount}</span>
                      </div>
                      <div>
                        <span className="text-blue-700 dark:text-blue-300">Categorical:</span>
                        <span className="ml-1 font-medium dark:text-blue-100">{categoricalCount}</span>
                      </div>
                      <div>
                        <span className="text-blue-700 dark:text-blue-300">Date:</span>
                        <span className="ml-1 font-medium dark:text-blue-100">{dateCount}</span>
                      </div>
                    </div>
                  );
                })()}
                {datasetAnalysis.suggestedTargetVariable && (
                  <div className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                    <span>Suggested target variable: </span>
                    <span className="font-medium dark:text-blue-100">{datasetAnalysis.suggestedTargetVariable}</span>
                  </div>
                )}
              </div>
            )}

            {/* Confirm Button and Execution Flow */}
            {(workflowPath === 'platform_split' || workflowPath === 'pre_split') && datasetAnalysis && (
              <div className="md:col-span-2 lg:col-span-3">
                {/* Confirm: hide orange button while confirming and after success */}
                {!splitConfirmationState.isConfirmed && (
                  <div className="flex flex-col items-center space-y-3">
                    {splitConfirmationState.isConfirming ? (
                      <div className="flex items-center space-x-2 py-3 text-sm text-gray-600 dark:text-gray-400">
                        <Loader2 className="h-5 w-5 animate-spin text-orange-500" />
                        <span>Confirming partition configuration…</span>
                      </div>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={handleConfirmSplit}
                          disabled={!canConfirmSplit}
                          className="px-8 py-3 bg-gradient-to-r from-orange-400 to-orange-500 text-white font-medium rounded-full shadow-lg hover:from-orange-500 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2"
                        >
                          <Check className="h-5 w-5" />
                          <span>Confirm</span>
                        </button>
                        <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
                          You can return and reconfigure at any time before model training begins.
                        </p>
                      </>
                    )}
                  </div>
                )}

                {/* Error Message */}
                {splitConfirmationState.error && (
                  <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                    <div className="flex items-start space-x-2">
                      <AlertCircle className="h-5 w-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-red-800 dark:text-red-200">Confirmation Failed</p>
                        <p className="text-sm text-red-700 dark:text-red-300 mt-1">{splitConfirmationState.error}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Partition Stats after confirmation */}
                {splitConfirmationState.isConfirmed && splitConfirmationState.stats && (
                  <div className="mt-6 bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <h6 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Partition Statistics</h6>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                        <p className="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-wide">Train</p>
                        <p className="text-lg font-bold text-blue-700 dark:text-blue-300">
                          {splitConfirmationState.stats.trainRows.toLocaleString()}
                        </p>
                        <p className="text-xs text-blue-500 dark:text-blue-400">rows</p>
                      </div>
                      <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 text-center">
                        <p className="text-xs text-green-600 dark:text-green-400 uppercase tracking-wide">Test</p>
                        <p className="text-lg font-bold text-green-700 dark:text-green-300">
                          {splitConfirmationState.stats.testRows.toLocaleString()}
                        </p>
                        <p className="text-xs text-green-500 dark:text-green-400">rows</p>
                      </div>
                      <div className="bg-amber-50 dark:bg-amber-900/30 rounded-lg p-3 text-center">
                        <p className="text-xs text-amber-600 dark:text-amber-400 uppercase tracking-wide">Validation</p>
                        <p className="text-lg font-bold text-amber-700 dark:text-amber-300">
                          {splitConfirmationState.stats.validationRows.toLocaleString()}
                        </p>
                        <p className="text-xs text-amber-500 dark:text-amber-400">rows</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>

          {hasStagedDataset && (
            <div className="mt-6">
              <UserKnowledgeUploadPanel
                datasetId={activeDatasetId}
                scope="objectives"
                mode="staged"
                files={stagedUserKnowledgeFiles}
                useAcrossMidas={stagedUseAcrossMidas}
                useExlExpertise={stagedUseExlExpertise}
                onFilesChange={setStagedUserKnowledgeFiles}
                onToggleChange={({ useAcrossMidas, useExlExpertise }) => {
                  setStagedUseAcrossMidas(useAcrossMidas);
                  setStagedUseExlExpertise(useExlExpertise);
                }}
              />
            </div>
          )}

          <div className="mt-6 flex items-center justify-between">
            <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>{selectedDataSources.length} data source{selectedDataSources.length !== 1 ? 's' : ''} selected</span>
            </div>
            {!(activeDatasetId || pendingDatasetId) && (
              <button
                type="button"
                onClick={onSubmitDataset}
                disabled={
                  isUploadingDataset ||
                  !canSubmitDataset ||
                  (((workflowPath === 'platform_split' || workflowPath === 'pre_split') &&
                    datasetAnalysis) &&
                    !splitConfirmationState.isConfirmed)
                }
                title={
                  (workflowPath === 'platform_split' || workflowPath === 'pre_split') &&
                  datasetAnalysis &&
                  !splitConfirmationState.isConfirmed
                    ? 'Confirm your data partition before submitting.'
                    : !canSubmitDataset && submitBlockedReason
                      ? submitBlockedReason
                      : undefined
                }
                className="px-6 py-2 bg-green-600 dark:bg-[#81689D] text-white dark:text-[#ccccff] rounded-lg hover:bg-green-700 dark:hover:bg-[#9678b3] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
              >
                {isUploadingDataset ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    <span>Uploading…</span>
                  </>
                ) : (
                  <>
                    <span>Submit</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            )}
          </div>
          {submitValidationError && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">{submitValidationError}</p>
          )}

          {showPostSubmitMlSection && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">ML problem type</p>
              <p className="text-sm text-gray-600 mb-3">
                Suggested after your dataset is uploaded. You can change the type if needed.
              </p>
              <div className="max-w-xl">
                <label className="block text-sm font-medium text-gray-700 mb-1">ML Problem Type</label>
                <select
                  value={
                    datasetConfig?.dataset_structure_type ||
                    (chatInputs['dataset_structure_type' as unknown as number] as unknown as string) ||
                    'others'
                  }
                  onChange={(e) => {
                    const newValue = e.target.value as 'classification' | 'regression' | 'time_series' | 'others';
                    setChatInputs((prev: any) => ({ ...prev, ['dataset_structure_type' as unknown as number]: newValue }));
                    if (datasetConfig) {
                      setDatasetConfig((prev: any) => (prev ? { ...prev, dataset_structure_type: newValue } : null));
                      sessionStorage.setItem(
                        'dataset_config',
                        JSON.stringify({ ...datasetConfig, dataset_structure_type: newValue })
                      );
                    }
                  }}
                  className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    (isAnalyzingDataset || mlClassificationPending) ? 'border-blue-300 bg-blue-50' : 'border-gray-300'
                  }`}
                  disabled={isAnalyzingDataset || mlClassificationPending}
                >
                  <option value="classification">Classification</option>
                  <option value="regression">Regression</option>
                  <option value="time_series">Time Series</option>
                  <option value="others">Others</option>
                </select>
                {(isAnalyzingDataset || mlClassificationPending) && (
                  <p className="mt-2 text-xs text-gray-500">Getting AI suggestion for problem type…</p>
                )}
                {!(isAnalyzingDataset || mlClassificationPending) && aiProblemTypeHint && (
                  <div className="mt-2 space-y-1">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-green-600">
                      <Bot className="h-4 w-4 shrink-0 text-violet-600" aria-hidden />
                      <span>
                        AI suggested:{' '}
                        {String(aiProblemTypeHint.dataset_type).replace(/_/g, ' ').toLowerCase()} (
                        {(() => {
                          const c = Number(aiProblemTypeHint.confidence);
                          const pct = c > 1 ? Math.round(c) : Math.round(c * 100);
                          return `${pct}%`;
                        })()}{' '}
                        confidence)
                      </span>
                    </p>
                    {aiProblemTypeHint.reasoning ? (
                      <p className="text-xs text-gray-500 italic pl-6 line-clamp-3" title={aiProblemTypeHint.reasoning}>
                        &ldquo;{aiProblemTypeHint.reasoning}&rdquo;
                      </p>
                    ) : null}
                  </div>
                )}
                {!(isAnalyzingDataset || mlClassificationPending) && mlClassificationErrorMessage && (
                  <p className="mt-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    {mlClassificationErrorMessage}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
};

export default Step1ObjectivesData;
