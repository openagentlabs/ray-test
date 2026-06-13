import React, { useState, useEffect, useRef, useMemo } from 'react';
import { AlertTriangle, CheckCircle, Search, X, ChevronDown, SkipForward } from 'lucide-react';

/**
 * Interface for duplicate identification result
 */
interface DuplicateIdentificationResult {
  duplicateCount: number;
  totalRows: number;
  duplicatePercentage: number;
  selectedColumns: string[];
  /** 'train' | 'entire' — where the preview count was computed (backend identify-duplicates) */
  analysisScope: 'train' | 'entire' | string;
}

/**
 * Props for DuplicateRemovalPanel component
 */
interface DuplicateRemovalPanelProps {
  /** Dataset ID for API calls */
  datasetId: string | null;
  /** Available columns from dataset (excluding data split identifier) */
  availableColumns: string[];
  /** Data split identifier column name (to exclude from selection) */
  dataSplitColumn?: string;
  /** Callback when duplicates are removed */
  onDuplicatesRemoved: (result: { removedCount: number; newRowCount: number }) => void;
  /** Callback when user selects Yes/No for duplicate removal */
  onSelectionChange: (wantsToRemove: boolean | null) => void;
  /** Current selection state (lifted) */
  wantsToRemoveDuplicates: boolean | null;
  /** Whether duplicate removal is complete (lifted) */
  isDuplicateRemovalComplete: boolean;
  /** Whether user skipped duplicate removal (lifted) */
  isSkipped: boolean;
  /** Callback when user clicks Skip */
  onSkip: () => void;
  /** Callback to trigger sidebar open */
  onOpenSidebar?: () => void;
  /** Removal result (lifted) */
  removalResult?: { removedCount: number; newRowCount: number } | null;

  // ── Lifted state for full persistence ──────────────────────────────────────
  selectedVariables: string[];
  onSelectedVariablesChange: (v: string[]) => void;
  identificationResult: DuplicateIdentificationResult | null;
  onIdentificationResultChange: (v: DuplicateIdentificationResult | null) => void;
}

/**
 * DuplicateRemovalPanel — handles the full duplicate removal workflow.
 *
 * All meaningful state (criteria, selected variables, identification result,
 * Yes/No answer, completion flag) is lifted to ModelBuilder so it persists
 * across page navigation.
 *
 * Once removal or skip is completed the entire panel becomes read-only —
 * no further changes are allowed for the current dataset.
 */
const DuplicateRemovalPanel: React.FC<DuplicateRemovalPanelProps> = ({
  datasetId,
  availableColumns,
  dataSplitColumn = 'data_split_identifier',
  onDuplicatesRemoved,
  onSelectionChange,
  wantsToRemoveDuplicates,
  isDuplicateRemovalComplete,
  isSkipped,
  onSkip,
  onOpenSidebar,
  removalResult,
  selectedVariables,
  onSelectedVariablesChange,
  identificationResult,
  onIdentificationResultChange,
}) => {
  // ── local UI-only state (not persisted — only transient interaction state) ──
  const [searchTerm, setSearchTerm] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isIdentifying, setIsIdentifying] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref for outside-click detection on the variable dropdown
  const dropdownRef = useRef<HTMLDivElement>(null);

  /** True when the panel is locked (no further changes allowed) */
  const isLocked = isDuplicateRemovalComplete || isSkipped;

  // ── derived columns ─────────────────────────────────────────────────────────
  const filteredColumns = useMemo(
    () => availableColumns.filter(col => col !== dataSplitColumn),
    [availableColumns, dataSplitColumn]
  );

  const searchFilteredColumns = useMemo(() => {
    if (!searchTerm.trim()) return filteredColumns;
    const lower = searchTerm.toLowerCase();
    return filteredColumns.filter(col => col.toLowerCase().includes(lower));
  }, [filteredColumns, searchTerm]);

  // ── effects ─────────────────────────────────────────────────────────────────

  // Reset transient UI state when the dataset changes
  useEffect(() => {
    setSearchTerm('');
    setIsDropdownOpen(false);
    setError(null);
  }, [datasetId]);

  // Close dropdown when user clicks outside
  useEffect(() => {
    if (!isDropdownOpen) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isDropdownOpen]);

  // ── handlers ─────────────────────────────────────────────────────────────────

  const handleVariableToggle = (variable: string) => {
    if (isLocked) return;
    const updated = selectedVariables.includes(variable)
      ? selectedVariables.filter(v => v !== variable)
      : [...selectedVariables, variable];
    onSelectedVariablesChange(updated);
    onIdentificationResultChange(null);
  };

  const handleSelectAll = () => {
    if (isLocked) return;
    onSelectedVariablesChange(searchFilteredColumns);
    onIdentificationResultChange(null);
  };

  const handleClearAll = () => {
    if (isLocked) return;
    onSelectedVariablesChange([]);
    onIdentificationResultChange(null);
  };

  const handleIdentifyDuplicates = async () => {
    if (!datasetId || isLocked) { setError('No dataset selected'); return; }

    // Always use selectedVariables since criteria dropdown was removed
    const columnsToCheck = selectedVariables;
    if (columnsToCheck.length === 0) { setError('Please select at least one variable'); return; }

    setIsIdentifying(true);
    setError(null);
    try {
      const { fastApiService } = await import('../services/fastApiService');
      const result = await fastApiService.identifyDuplicates(datasetId, columnsToCheck);
      onIdentificationResultChange({
        duplicateCount: result.duplicate_count,
        totalRows: result.total_rows,
        duplicatePercentage: result.duplicate_percentage,
        selectedColumns: columnsToCheck,
        analysisScope: result.analysis_scope === 'entire' ? 'entire' : 'train',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to identify duplicates');
    } finally {
      setIsIdentifying(false);
    }
  };

  const handleRemoveDuplicates = async () => {
    if (!datasetId || !identificationResult || isLocked) { setError('No duplicates identified'); return; }

    setIsRemoving(true);
    setError(null);
    try {
      const { fastApiService } = await import('../services/fastApiService');
      const result = await fastApiService.removeDuplicates(datasetId, identificationResult.selectedColumns);
      onDuplicatesRemoved({ removedCount: result.removed_count, newRowCount: result.new_row_count });
      if (onOpenSidebar) onOpenSidebar();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove duplicates');
    } finally {
      setIsRemoving(false);
    }
  };

  // ── derived display flags ────────────────────────────────────────────────────

  const showCriteriaSection = wantsToRemoveDuplicates === true;
  // Action buttons are shown only when not yet locked
  const showActionButtons = !isLocked;

  // ── render ───────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* ── Main panel ── */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-6">

        {/* Header */}
        <div className="border-b border-gray-200 dark:border-gray-700 pb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Duplicate Removal</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Do you want to remove duplicate observations?
          </p>
        </div>

        {/* Yes / No radio buttons */}
        <div className="flex items-center space-x-6">
          <label className={`flex items-center space-x-2 ${isLocked ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}>
            <input
              type="radio"
              name="removeDuplicates"
              checked={wantsToRemoveDuplicates === true}
              onChange={() => !isLocked && onSelectionChange(true)}
              disabled={isLocked}
              className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <span className="text-gray-700 dark:text-gray-300 font-medium">Yes</span>
          </label>
          <label className={`flex items-center space-x-2 ${isLocked ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}>
            <input
              type="radio"
              name="removeDuplicates"
              checked={wantsToRemoveDuplicates === false}
              onChange={() => !isLocked && onSelectionChange(false)}
              disabled={isLocked}
              className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <span className="text-gray-700 dark:text-gray-300 font-medium">No</span>
          </label>
        </div>

        {/* ── Yes flow ── */}
        {showCriteriaSection && (
          <div className="space-y-4 pt-4 border-t border-gray-200 dark:border-gray-700">

            {/* Variable multi-select */}
            {
              <div className={`relative ${isLocked ? 'pointer-events-none opacity-70' : ''}`} ref={dropdownRef}>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Select Variables ({selectedVariables.length} selected)
                </label>

                {/* Trigger button */}
                <button
                  type="button"
                  onClick={() => !isLocked && setIsDropdownOpen(prev => !prev)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                             bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
                             focus:outline-none focus:ring-2 focus:ring-blue-500
                             flex items-center justify-between"
                >
                  <span className="truncate">
                    {selectedVariables.length === 0
                      ? 'Click to select variables…'
                      : `${selectedVariables.length} variable(s) selected`}
                  </span>
                  <ChevronDown className={`h-4 w-4 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown panel */}
                {isDropdownOpen && !isLocked && (
                  <div className="absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300
                                 dark:border-gray-600 rounded-lg shadow-lg max-h-80 flex flex-col">
                    {/* Search */}
                    <div className="p-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
                      <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <input
                          type="text"
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          placeholder="Search variables…"
                          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600
                                     rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                                     focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                    </div>

                    {/* Select All / Clear All */}
                    <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 shrink-0">
                      <button type="button" onClick={handleSelectAll} className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400">Select All</button>
                      <button type="button" onClick={handleClearAll} className="text-xs text-red-600 hover:text-red-700 dark:text-red-400">Clear All</button>
                    </div>

                    {/* Column list - scrollable */}
                    <div className="overflow-y-auto flex-1 min-h-0">
                      {searchFilteredColumns.length === 0 ? (
                        <div className="px-3 py-4 text-center text-sm text-gray-500 dark:text-gray-400">No variables found</div>
                      ) : (
                        searchFilteredColumns.map((column) => (
                          <label key={column} className="flex items-center px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedVariables.includes(column)}
                              onChange={() => handleVariableToggle(column)}
                              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            />
                            <span className="ml-2 text-sm text-gray-700 dark:text-gray-300 truncate">{column}</span>
                          </label>
                        ))
                      )}
                    </div>

                    {/* Done button - fixed at bottom */}
                    <div className="p-2 border-t border-gray-200 dark:border-gray-700 shrink-0">
                      <button
                        type="button"
                        onClick={() => setIsDropdownOpen(false)}
                        className="w-full px-3 py-1.5 text-sm bg-blue-600 dark:bg-blue-700
                                   text-white rounded hover:bg-blue-700
                                   dark:hover:bg-blue-600 transition-colors font-medium"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}

                {/* Selected variable tags */}
                {selectedVariables.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {selectedVariables.slice(0, 5).map((variable) => (
                      <span key={variable} className="inline-flex items-center px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-full">
                        {variable}
                        {!isLocked && (
                          <button type="button" onClick={() => handleVariableToggle(variable)} className="ml-1 hover:text-blue-600 dark:hover:text-blue-200">
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </span>
                    ))}
                    {selectedVariables.length > 5 && (
                      <span className="text-xs text-gray-500 dark:text-gray-400 py-1">+{selectedVariables.length - 5} more</span>
                    )}
                  </div>
                )}
              </div>
            }

            {/* ── Action buttons — only shown when not locked ── */}
            {showActionButtons && (
              <>
                <button
                  type="button"
                  onClick={handleIdentifyDuplicates}
                  disabled={isIdentifying || selectedVariables.length === 0}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                             disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                             flex items-center space-x-2"
                >
                  {isIdentifying ? (
                    <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /><span>Identifying…</span></>
                  ) : (
                    <span>Identify Duplicates</span>
                  )}
                </button>

                {error && (
                  <div className="flex items-center space-x-2 text-red-600 dark:text-red-400 text-sm">
                    <AlertTriangle className="h-4 w-4" />
                    <span>{error}</span>
                  </div>
                )}
              </>
            )}

            {/* ── Identification result pane (orange) — always shown once identified ── */}
            {identificationResult && (
              <div className="space-y-4">
                <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded-lg p-4">
                  <div className="flex items-start space-x-3">
                    <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-400 mt-0.5 flex-shrink-0" />
                    <div>
                      {(() => {
                        const analysisScope = identificationResult.analysisScope ?? 'train';
                        return (
                          <>
                            <p className="text-orange-800 dark:text-orange-200 font-medium">
                              {analysisScope === 'entire' ? (
                                <>
                                  In the <span className="font-semibold">full dataset</span> (no train/test split), we
                                  identified{' '}
                                  <span className="font-bold">{identificationResult.duplicateCount.toLocaleString()}</span>{' '}
                                  duplicate rows using your selected columns.
                                </>
                              ) : (
                                <>
                                  In the <span className="font-semibold">training split only</span>, we identified{' '}
                                  <span className="font-bold">{identificationResult.duplicateCount.toLocaleString()}</span>{' '}
                                  duplicate rows using your selected columns.
                                </>
                              )}
                            </p>
                            <p className="text-sm text-orange-600 dark:text-orange-400 mt-1">
                              ({identificationResult.duplicatePercentage.toFixed(2)}% of{' '}
                              {identificationResult.totalRows.toLocaleString()}{' '}
                              {analysisScope === 'entire' ? 'rows' : 'training rows in that split'}).
                            </p>
                            {analysisScope === 'train' && (
                              <p className="text-xs text-orange-700/90 dark:text-orange-300/90 mt-2 leading-relaxed">
                                When you remove duplicates, the same rule is applied{' '}
                                <span className="font-medium">separately</span> to training, validation, and test. The
                                total rows removed can be higher than this preview.
                              </p>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  </div>
                </div>

                {/* Remove Duplicates + Skip — only when not locked */}
                {showActionButtons && identificationResult.duplicateCount > 0 && (
                  <div className="flex items-center space-x-3">
                    <button
                      type="button"
                      onClick={handleRemoveDuplicates}
                      disabled={isRemoving}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700
                                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                                 flex items-center space-x-2"
                    >
                      {isRemoving ? (
                        <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /><span>Removing…</span></>
                      ) : (
                        <span>Remove Duplicates</span>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={onSkip}
                      disabled={isRemoving}
                      className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300
                                 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600
                                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                                 flex items-center space-x-2"
                    >
                      <SkipForward className="h-4 w-4" />
                      <span>Skip</span>
                    </button>
                  </div>
                )}

                {/* No duplicates found */}
                {showActionButtons && identificationResult.duplicateCount === 0 && (
                  <div className="flex items-center space-x-2 text-green-600 dark:text-green-400">
                    <CheckCircle className="h-5 w-5" />
                    <span>No duplicates found! Your data is clean.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* No selected */}
        {wantsToRemoveDuplicates === false && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              You have chosen not to remove duplicates. You can proceed to the next steps.
            </p>
          </div>
        )}
      </div>

      {/* ── Success pane — appended below after removal ── */}
      {isDuplicateRemovalComplete && removalResult && (
        <div className="bg-green-50 dark:bg-green-900/20 rounded-xl border border-green-200 dark:border-green-700 p-5">
          <div className="flex items-center space-x-3">
            <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400 flex-shrink-0" />
            <div>
              <h4 className="text-base font-semibold text-green-800 dark:text-green-200">
                Duplicate Removal Complete
              </h4>
              <p className="text-sm text-green-600 dark:text-green-400 mt-0.5">
                Successfully removed{' '}
                <span className="font-bold">{removalResult.removedCount.toLocaleString()}</span> duplicate rows.
                Dataset now has{' '}
                <span className="font-bold">{removalResult.newRowCount.toLocaleString()}</span> rows.
                Check the sidebar for EDA comparison.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Skip pane — appended below when user skips ── */}
      {isSkipped && (
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-700 p-5">
          <div className="flex items-center space-x-3">
            <SkipForward className="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
            <p className="text-sm text-blue-700 dark:text-blue-300">
              Duplicate treatment skipped. You can proceed to the next steps.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default DuplicateRemovalPanel;
