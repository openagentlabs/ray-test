import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { ChevronDown, X, Loader, Database, Settings, Wand2, PenLine, GripVertical, Plus, Trash2, AlertTriangle, CheckCircle2, Info, ArrowRight, ListPlus } from 'lucide-react';
import { fastApiService, SegmentationModeType, UnifiedSegmentationRequest, UnifiedSegmentationResponse, VariablePriority, ManualSegmentRule, RuleCondition, RuleValidationResult, DatasetColumnInfo } from '../../services/fastApiService';
import { formatSegmentationChiSquaredPLabel, formatSegmentationTotalIv } from '../../utils/segmentationMetricsDisplay';

interface Step3_5SegmentationAgentAnalysisProps {
  datasetPreview: any;
  
  // Problem type detection
  problemType?: 'classification' | 'regression';
  
  activeDatasetId?: string;
  targetVariable?: string;
  
  // Segmentation mode toggle (legacy - still supported for backward compatibility)
  segmentationMode: 'custom' | 'auto';
  setSegmentationMode: (mode: 'custom' | 'auto') => void;
  
  // Custom segmentation props
  availableColumns?: string[];
  /** Per-column analysis (Step 1); used to filter C1 Pre-existing Identifier dropdown */
  columnMetadata?: DatasetColumnInfo[];
  selectedSegmentationVariables: string[];
  setSelectedSegmentationVariables: (cols: string[]) => void;
  segmentationMethod: 'cart' | 'chaid';
  setSegmentationMethod: (m: 'cart' | 'chaid') => void;
  minSegmentSize: number;
  setMinSegmentSize: (size: number) => void;
  maxSegments: number;
  setMaxSegments: (count: number) => void;
  
  // Minimum segment size mode and percentage props
  minSegmentSizeMode: 'number' | 'percentage';
  setMinSegmentSizeMode: (mode: 'number' | 'percentage') => void;
  minSegmentSizePercentage: number;
  setMinSegmentSizePercentage: (percentage: number) => void;
  onRunSegmentation: () => Promise<void> | void;
  isRunningSegmentation?: boolean;
  
  // Auto segmentation props
  onRunAutoSegmentation?: () => Promise<void> | void;
  isRunningAutoSegmentation?: boolean;
  
  // Segmentation result - now using unified response type
  segmentationResult?: UnifiedSegmentationResponse | any;
  
  // Callback to update segmentation result in parent
  onSegmentationResult?: (result: UnifiedSegmentationResponse | null) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

/** C1 Pre-existing Identifier: allowed = categorical (non-date) OR cardinality ≤ this */
const PRE_EXISTING_MAX_CARDINALITY = 50;

function isCategoricalForPreExisting(col: DatasetColumnInfo): boolean {
  if (col.is_date || (col.logical_type as string) === 'Date') return false;
  return col.type === 'Categorical' || col.logical_type === 'Categorical';
}

function isPreExistingIdentifierColumn(col: DatasetColumnInfo, targetVariable?: string): boolean {
  if (targetVariable && col.name === targetVariable) return false;
  const n = col.unique_count;
  if (n != null && Number.isFinite(Number(n)) && Number(n) >= 1 && Number(n) <= PRE_EXISTING_MAX_CARDINALITY) {
    return true;
  }
  return isCategoricalForPreExisting(col);
}

function estimateUniqueFromPreviewSample(colName: string, datasetPreview: any): number | null {
  const rows = datasetPreview?.preview_data?.rows;
  const cols: string[] = datasetPreview?.preview_data?.columns;
  if (!Array.isArray(rows) || !Array.isArray(cols) || rows.length === 0) return null;
  if (!cols.includes(colName)) return null;
  const set = new Set<unknown>();
  for (const row of rows) {
    if (row && typeof row === 'object' && colName in (row as object)) {
      set.add((row as Record<string, unknown>)[colName]);
    }
  }
  return set.size;
}

const Step3_5SegmentationAgentAnalysis: React.FC<Step3_5SegmentationAgentAnalysisProps> = ({
  datasetPreview,
  problemType,
  activeDatasetId,
  targetVariable,
  segmentationMode,
  availableColumns = [],
  columnMetadata,
  selectedSegmentationVariables,
  setSelectedSegmentationVariables,
  segmentationMethod,
  setSegmentationMethod,
  minSegmentSize,
  setMinSegmentSize,
  maxSegments,
  setMaxSegments,
  minSegmentSizeMode,
  setMinSegmentSizeMode,
  minSegmentSizePercentage,
  setMinSegmentSizePercentage,
  isRunningSegmentation = false,
  onRunAutoSegmentation,
  isRunningAutoSegmentation = false,
  segmentationResult,
  onSegmentationResult,
  renderStepChat
}) => {
  const [isPreviewOpen, setIsPreviewOpen] = useState<boolean>(true);
  const [isSegmentedPreviewOpen, setIsSegmentedPreviewOpen] = useState<boolean>(false);
  const [segmentedDatasetPreview, setSegmentedDatasetPreview] = useState<any>(null);
  const [isLoadingSegmentedPreview, setIsLoadingSegmentedPreview] = useState<boolean>(false);

  // =============================================================================
  // NEW: 4-Mode Segmentation Agent State
  // =============================================================================
  
  // Current segmentation mode (4 modes)
  const [agentMode, setAgentMode] = useState<SegmentationModeType>('variable_driven');
  
  // C1: Pre-existing Identifier mode state
  const [selectedSegmentColumn, setSelectedSegmentColumn] = useState<string>('');
  
  // C2: Variable-Driven mode state
  const [variablePriority, setVariablePriority] = useState<VariablePriority>({ primary: '', secondary: null, tertiary: null });
  
  // C3: Manual Rules mode state
  const [manualRules, setManualRules] = useState<ManualSegmentRule[]>([
    { segment_name: 'Segment 1', conditions: [{ variable: '', operator: '==', value: '' }], logic: 'AND', catch_all: false }
  ]);
  const [dragRuleIndex, setDragRuleIndex] = useState<number | null>(null);
  const [ruleValidationResult, setRuleValidationResult] = useState<RuleValidationResult | null>(null);
  
  // Auto mode state
  const [autoCandidates, setAutoCandidates] = useState<any[]>([]);
  const [selectedAutoScheme, setSelectedAutoScheme] = useState<number | null>(null);
  const [promotionSuggestions, setPromotionSuggestions] = useState<any[]>([]);
  const [splitterSelectionTrail, setSplitterSelectionTrail] = useState<string[]>([]);
  
  // Unified segmentation loading state
  const [isRunningUnifiedSegmentation, setIsRunningUnifiedSegmentation] = useState<boolean>(false);
  const [segmentationError, setSegmentationError] = useState<string | null>(null);
  const [segmentationStartTime, setSegmentationStartTime] = useState<number | null>(null);
  
  // Scheme Registry Panel state
  const [savedSchemes, setSavedSchemes] = useState<any[]>([]);
  const [isLoadingSchemes, setIsLoadingSchemes] = useState<boolean>(false);
  const [isSchemeRegistryExpanded, setIsSchemeRegistryExpanded] = useState<boolean>(true);
  const [selectedSchemeDetails, setSelectedSchemeDetails] = useState<any | null>(null);
  const [isSchemeDetailsModalOpen, setIsSchemeDetailsModalOpen] = useState<boolean>(false);
  const [isLoadingSchemeDetails, setIsLoadingSchemeDetails] = useState<boolean>(false);
  const [schemeDetailRawJson, setSchemeDetailRawJson] = useState<string>('');

  // Mode descriptions for UI
  const segmentationModes: Array<{
    mode: SegmentationModeType;
    label: string;
    shortLabel: string;
    description: string;
    icon: React.ElementType;
    color: string;
  }> = [
    {
      mode: 'pre_existing',
      label: 'Pre-existing Identifier',
      shortLabel: 'C1',
      description: 'Use an existing column in your dataset as segment identifier',
      icon: Database,
      color: 'blue'
    },
    {
      mode: 'variable_driven',
      label: 'Variable-Driven',
      shortLabel: 'C2',
      description: 'Build segments using decision trees with priority variable ordering',
      icon: Settings,
      color: 'purple'
    },
    {
      mode: 'manual_rules',
      label: 'Manual Rules',
      shortLabel: 'C3',
      description: 'Define custom segment rules using SQL-style conditions',
      icon: PenLine,
      color: 'green'
    },
    {
      mode: 'auto',
      label: 'Auto Segmentation',
      shortLabel: 'Auto',
      description: 'Let the system automatically discover optimal segmentation schemes',
      icon: Wand2,
      color: 'amber'
    }
  ];
  
  // Operator options for manual rules (plan §6.2)
  const operatorOptions = [
    { value: '<=', label: '<=' },
    { value: '>=', label: '>=' },
    { value: '<', label: '<' },
    { value: '>', label: '>' },
    { value: '==', label: '= / ==' },
    { value: '!=', label: '!=' },
    { value: 'between', label: 'BETWEEN' },
    { value: 'not_between', label: 'NOT BETWEEN' },
    { value: 'in', label: 'IN (...)' },
    { value: 'not_in', label: 'NOT IN (...)' },
    { value: 'is_true', label: '= TRUE' },
    { value: 'is_false', label: '= FALSE' },
    { value: 'contains', label: 'contains (text)' },
    { value: 'is_null', label: 'IS NULL' },
    { value: 'is_not_null', label: 'IS NOT NULL' },
  ];

  // Minimum segment size mode and percentage are now passed as props

  // Local UI state for segmentation dropdown
  const [isDropdownOpen, setIsDropdownOpen] = useState<boolean>(false);

  // Automatically set scope to 'entire' when component mounts (Segmentation always uses entire dataset)
  useEffect(() => {
    const setScopeToEntire = async () => {
      if (!activeDatasetId) return;
      
      try {
        await fastApiService.setDatasetScope({ 
          dataset_id: activeDatasetId, 
          scope: 'entire',
          seed: 42 
        });
        // Trigger refresh event to update previews
        window.dispatchEvent(new CustomEvent('datasetScopeChanged', { 
          detail: { dataset_id: activeDatasetId, scope: 'entire' } 
        }));
      } catch (error) {
        console.error('Failed to set scope to entire in Segmentation:', error);
        // Don't show error to user, just log it
      }
    };
    
    setScopeToEntire();
  }, [activeDatasetId]);

  // Load segmented dataset preview
  const loadSegmentedDatasetPreview = async () => {
    if (!activeDatasetId) return;
    
    setIsLoadingSegmentedPreview(true);
    try {
      const response = await fastApiService.getSegmentedDatasetPreview(activeDatasetId);
      if (response.success) {
        setSegmentedDatasetPreview(response);
        setIsSegmentedPreviewOpen(true);
      }
    } catch (error) {
      console.error('Failed to load segmented dataset preview:', error);
      // Don't show error to user, just log it
    } finally {
      setIsLoadingSegmentedPreview(false);
    }
  };
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const [variableSearch, setVariableSearch] = useState<string>('');
  
  // Local UI state for auto segmentation variables (default to all)
  const [selectedAutoSegmentationVariables, setSelectedAutoSegmentationVariables] = useState<string[]>(availableColumns || []);
  const [autoSegmentationSearch, setAutoSegmentationSearch] = useState<string>('');
  const [isAutoDropdownOpen, setIsAutoDropdownOpen] = useState<boolean>(false);
  const autoDropdownRef = useRef<HTMLDivElement | null>(null);

  const preExistingIdentifierOptions = useMemo(() => {
    const t = targetVariable;
    if (columnMetadata && columnMetadata.length > 0) {
      return columnMetadata
        .filter((c) => isPreExistingIdentifierColumn(c, t))
        .map((c) => c.name)
        .filter((name) => (availableColumns || []).includes(name));
    }
    if (datasetPreview) {
      return (availableColumns || []).filter((name) => {
        if (name === t) return false;
        const u = estimateUniqueFromPreviewSample(name, datasetPreview);
        if (u == null) return false;
        return u <= PRE_EXISTING_MAX_CARDINALITY;
      });
    }
    return [];
  }, [columnMetadata, availableColumns, targetVariable, datasetPreview]);

  useEffect(() => {
    if (agentMode !== 'pre_existing') return;
    if (selectedSegmentColumn && !preExistingIdentifierOptions.includes(selectedSegmentColumn)) {
      setSelectedSegmentColumn('');
    }
  }, [agentMode, preExistingIdentifierOptions, selectedSegmentColumn]);

  // Sync auto segmentation variables with available columns (default to all)
  useEffect(() => {
    if (availableColumns && availableColumns.length > 0) {
      // Filter selected variables to only include those that still exist
      const filtered = selectedAutoSegmentationVariables.filter(v => availableColumns.includes(v));
      
      // If we filtered out variables or if nothing is selected, update to all available
      if (filtered.length !== selectedAutoSegmentationVariables.length || filtered.length === 0) {
        setSelectedAutoSegmentationVariables(availableColumns);
      }
    }
  }, [availableColumns]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setIsDropdownOpen(false);
      if (autoDropdownRef.current && !autoDropdownRef.current.contains(e.target as Node)) setIsAutoDropdownOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  // Load segmented dataset preview when segmentation is completed
  useEffect(() => {
    // Check if segmentation was just completed (not running anymore and we have a dataset)
    if (!isRunningSegmentation && !isRunningAutoSegmentation && activeDatasetId) {
      // Small delay to ensure backend has processed the segmentation
      const timer = setTimeout(() => {
        loadSegmentedDatasetPreview();
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isRunningSegmentation, isRunningAutoSegmentation, activeDatasetId]);

  // Refresh dataset preview when scope changes
  useEffect(() => {
    const handleScopeChange = async (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail?.dataset_id === activeDatasetId) {
        // Reload dataset preview after scope change
        if (datasetPreview) {
          // Reload the preview by calling the API
          try {
            if (!activeDatasetId) return;
            const response = await fastApiService.getDatasetPreview(activeDatasetId);
            if (response.success) {
              // Update local state or trigger re-render
              // The preview will be updated through props from ModelBuilder
            }
          } catch (error) {
            console.error('Failed to reload dataset preview after scope change:', error);
          }
        }
      }
    };

    window.addEventListener('datasetScopeChanged', handleScopeChange);
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange);
    };
  }, [activeDatasetId, datasetPreview]);
  
  // Load saved segmentation schemes for the Scheme Registry Panel
  const loadSavedSchemes = useCallback(async () => {
    if (!activeDatasetId) return;
    
    setIsLoadingSchemes(true);
    try {
      const response = await fastApiService.getSegmentationSchemes(activeDatasetId);
      if (response.success) {
        setSavedSchemes(response.schemes || []);
      }
    } catch (error) {
      console.error('Failed to load saved schemes:', error);
      setSavedSchemes([]);
    } finally {
      setIsLoadingSchemes(false);
    }
  }, [activeDatasetId]);
  
  // Load schemes on mount and when dataset changes
  useEffect(() => {
    loadSavedSchemes();
  }, [loadSavedSchemes]);
  
  // Refresh schemes after adding to data (listen for custom event)
  useEffect(() => {
    const handleSchemeAdded = () => {
      loadSavedSchemes();
    };
    
    window.addEventListener('segmentationSchemeAdded', handleSchemeAdded);
    return () => {
      window.removeEventListener('segmentationSchemeAdded', handleSchemeAdded);
    };
  }, [loadSavedSchemes]);
  
  const handleViewSchemeDetails = useCallback(
    async (scheme: any) => {
      setSelectedSchemeDetails(scheme);
      setSchemeDetailRawJson('');
      setIsSchemeDetailsModalOpen(true);
      if (!activeDatasetId || scheme?.scheme_id == null) return;
      setIsLoadingSchemeDetails(true);
      try {
        const detail = await fastApiService.getSegmentationSchemeDetail(activeDatasetId, scheme.scheme_id);
        if (detail.success && detail.metadata) {
          const m = detail.metadata as Record<string, any>;
          const val = (m.validation || {}) as Record<string, any>;
          setSelectedSchemeDetails({
            scheme_id: m.scheme_id,
            column_name: m.column_name ?? scheme.column_name,
            mode: m.mode,
            variables: m.variables ?? [],
            variable_priority: m.variable_priority,
            segment_count: Array.isArray(m.segments) ? m.segments.length : scheme.segment_count,
            total_iv: m.total_iv ?? val.total_iv,
            recommendation_category: m.recommendation_category ?? val.recommendation_category,
            created_at: m.created_at,
            merge_history: m.merge_history ?? [],
            cutoff_edits: m.cutoff_edits ?? [],
            tree_method: m.tree_method,
            chi_squared_p: m.chi_squared_p,
            cramers_v: m.cramers_v,
            variable_selection_method: m.variable_selection_method,
            constraints_applied: m.constraints_applied,
            validation: m.validation,
            segments: m.segments,
            stability: m.stability ?? val.stability,
            holdout_validation: m.holdout_validation ?? val.oos_validation,
          });
          try {
            setSchemeDetailRawJson(JSON.stringify(m, null, 2));
          } catch {
            setSchemeDetailRawJson('');
          }
        } else if (detail.message) {
          setSelectedSchemeDetails({
            ...scheme,
            _detailMessage: detail.message,
          });
        }
      } catch (e) {
        console.warn('Scheme detail fetch failed', e);
      } finally {
        setIsLoadingSchemeDetails(false);
      }
    },
    [activeDatasetId]
  );

  const toggleVariable = (col: string) => {
    const exists = selectedSegmentationVariables.includes(col);
    const next = exists
      ? selectedSegmentationVariables.filter(c => c !== col)
      : [...selectedSegmentationVariables, col];
    setSelectedSegmentationVariables(next);
  };
  const selectAll = () => setSelectedSegmentationVariables([...(availableColumns || [])]);
  const clearAll = () => setSelectedSegmentationVariables([]);
  
  // Auto segmentation variable selection handlers
  const toggleAutoSegmentationVariable = (col: string) => {
    const exists = selectedAutoSegmentationVariables.includes(col);
    const next = exists
      ? selectedAutoSegmentationVariables.filter(c => c !== col)
      : [...selectedAutoSegmentationVariables, col];
    setSelectedAutoSegmentationVariables(next);
  };
  const selectAllAutoSegmentation = () => setSelectedAutoSegmentationVariables([...(availableColumns || [])]);
  const clearAllAutoSegmentation = () => setSelectedAutoSegmentationVariables([]);
  

  // =============================================================================
  // NEW: Unified Segmentation Handler for 4-Mode Architecture
  // =============================================================================
  
  const handleRunUnifiedSegmentation = useCallback(async () => {
    if (!activeDatasetId) {
      setSegmentationError('No dataset selected');
      return;
    }
    
    // Clear previous error and start timing
    setSegmentationError(null);
    setSegmentationStartTime(Date.now());
    setIsRunningUnifiedSegmentation(true);
    
    try {
      const request: UnifiedSegmentationRequest = {
        dataset_id: activeDatasetId,
        mode: agentMode,
        target_variable: targetVariable || null,
        method: segmentationMethod,
        min_segment_size: minSegmentSizeMode === 'percentage' ? undefined : minSegmentSize,
        min_segment_size_mode: minSegmentSizeMode === 'percentage' ? 'percentage' : 'absolute',
        min_segment_size_pct: minSegmentSizeMode === 'percentage' ? minSegmentSizePercentage : undefined,
        max_segments: maxSegments,
        max_depth: 3,  // Max depth limited to 3 per backend schema
      };
      
      // Add mode-specific parameters
      switch (agentMode) {
        case 'pre_existing':
          if (!selectedSegmentColumn) {
            setSegmentationError('Please select a segment column');
            setIsRunningUnifiedSegmentation(false);
            return;
          }
          request.segment_column = selectedSegmentColumn;
          break;
          
        case 'variable_driven':
          if (!variablePriority.primary) {
            setSegmentationError('Please select at least a primary variable');
            setIsRunningUnifiedSegmentation(false);
            return;
          }
          request.variable_priority = variablePriority;
          break;
          
        case 'manual_rules':
          const validRules = manualRules.filter(r =>
            r.segment_name &&
            (r.catch_all || r.conditions.some(c => c.variable && c.operator))
          );
          if (validRules.length === 0) {
            setSegmentationError('Please define at least one valid segment rule');
            setIsRunningUnifiedSegmentation(false);
            return;
          }
          request.manual_rules = validRules;
          break;
          
        case 'auto':
          // Auto mode doesn't need additional parameters
          break;
      }
      
      console.log('Running unified segmentation:', request);
      const result = await fastApiService.runUnifiedSegmentation(request);
      console.log('Unified segmentation result:', result);
      
      if (result.success) {
        // Clear any previous error
        setSegmentationError(null);
        
        // If in auto mode, store the candidates and any promotion suggestions
        if (agentMode === 'auto' && result.auto_candidates) {
          setAutoCandidates(result.auto_candidates);
          setSelectedAutoScheme(result.selected_scheme_rank || 0);
          
          // Handle promotion suggestions from sequential pipeline
          if ((result as any).promotion_suggestions) {
            setPromotionSuggestions((result as any).promotion_suggestions);
          }
          
          // Handle splitter selection trail from sequential pipeline
          if ((result as any).splitter_selection_trail) {
            setSplitterSelectionTrail((result as any).splitter_selection_trail);
          }
          
          // Also check for promotion suggestions in individual candidates
          const candidateSuggestions = result.auto_candidates
            .filter((c: any) => c.promotion_suggestion)
            .map((c: any) => c.promotion_suggestion);
          if (candidateSuggestions.length > 0) {
            setPromotionSuggestions(prev => [...prev, ...candidateSuggestions]);
          }
        } else {
          setAutoCandidates([]);
          setSelectedAutoScheme(null);
        }

        if (agentMode === 'variable_driven') {
          const ps = (result as any).promotion_suggestions;
          if (Array.isArray(ps) && ps.length > 0) {
            setPromotionSuggestions(ps);
          } else {
            const tps = result.tertiary_promotion_suggestion;
            setPromotionSuggestions(tps ? [tps] : []);
          }
        } else if (agentMode !== 'auto') {
          setPromotionSuggestions([]);
        }
        
        // Update parent component with result
        if (onSegmentationResult) {
          onSegmentationResult(result);
        }
        
        // Also trigger the legacy preview refresh
        loadSegmentedDatasetPreview();
      } else {
        setSegmentationError(`Segmentation failed: ${result.message}`);
      }
    } catch (error) {
      console.error('Error running unified segmentation:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setSegmentationError(errorMessage);
    } finally {
      setIsRunningUnifiedSegmentation(false);
      setSegmentationStartTime(null);
    }
  }, [activeDatasetId, agentMode, targetVariable, segmentationMethod, minSegmentSize, minSegmentSizeMode, minSegmentSizePercentage, maxSegments, selectedSegmentColumn, variablePriority, manualRules, onSegmentationResult]);
  
  // Validate manual rules in real-time
  const handleValidateRules = useCallback(async () => {
    if (!activeDatasetId || agentMode !== 'manual_rules') return;
    
    const validRules = manualRules.filter(r =>
      r.segment_name &&
      (r.catch_all || r.conditions.some(c => c.variable && c.operator))
    );
    
    if (validRules.length === 0) {
      setRuleValidationResult(null);
      return;
    }
    
    try {
      const request: UnifiedSegmentationRequest = {
        dataset_id: activeDatasetId,
        mode: 'manual_rules',
        manual_rules: validRules,
        target_variable: targetVariable || null,
      };
      
      const result = await fastApiService.validateSegmentationRules(request);
      setRuleValidationResult(result);
    } catch (error) {
      console.error('Error validating rules:', error);
    }
  }, [activeDatasetId, agentMode, manualRules, targetVariable]);
  
  // Debounced rule validation
  useEffect(() => {
    if (agentMode !== 'manual_rules') return;
    
    const timer = setTimeout(() => {
      handleValidateRules();
    }, 500);
    
    return () => clearTimeout(timer);
  }, [manualRules, agentMode, handleValidateRules]);
  
  // Manual rules handlers
  const addSegmentRule = useCallback(() => {
    setManualRules(prev => [
      ...prev,
      { 
        segment_name: `Segment ${prev.length + 1}`, 
        conditions: [{ variable: '', operator: '==', value: '' }], 
        logic: 'AND',
        catch_all: false,
      }
    ]);
  }, []);

  const addCatchAllSegment = useCallback(() => {
    setManualRules(prev => [
      ...prev,
      {
        segment_name: 'Catch-All',
        conditions: [],
        logic: 'AND',
        catch_all: true,
      },
    ]);
  }, []);

  const moveRule = useCallback((fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    setManualRules(prev => {
      const next = [...prev];
      const [row] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, row);
      return next;
    });
  }, []);
  
  const removeSegmentRule = useCallback((index: number) => {
    setManualRules(prev => prev.filter((_, i) => i !== index));
  }, []);
  
  const updateSegmentRule = useCallback((index: number, updates: Partial<ManualSegmentRule>) => {
    setManualRules(prev => prev.map((rule, i) => 
      i === index ? { ...rule, ...updates } : rule
    ));
  }, []);
  
  const addCondition = useCallback((ruleIndex: number) => {
    setManualRules(prev => prev.map((rule, i) => 
      i === ruleIndex 
        ? { ...rule, conditions: [...rule.conditions, { variable: '', operator: '==', value: '' }] }
        : rule
    ));
  }, []);
  
  const removeCondition = useCallback((ruleIndex: number, conditionIndex: number) => {
    setManualRules(prev => prev.map((rule, i) => 
      i === ruleIndex 
        ? { ...rule, conditions: rule.conditions.filter((_, ci) => ci !== conditionIndex) }
        : rule
    ));
  }, []);
  
  const updateCondition = useCallback((ruleIndex: number, conditionIndex: number, updates: Partial<RuleCondition>) => {
    setManualRules(prev => prev.map((rule, i) => 
      i === ruleIndex 
        ? { 
            ...rule, 
            conditions: rule.conditions.map((c, ci) => 
              ci === conditionIndex ? { ...c, ...updates } : c
            )
          }
        : rule
    ));
  }, []);

  // Auto-switch to CART if CHAID is selected but problem type is regression
  React.useEffect(() => {
    if (problemType === 'regression' && segmentationMethod === 'chaid') {
      setSegmentationMethod('cart');
    }
  }, [problemType, segmentationMethod, setSegmentationMethod]);

  return (
    <div className="space-y-6">
      {/* ============================================================= */}
      {/* SCHEME REGISTRY PANEL - Persistent panel at top of page */}
      {/* ============================================================= */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg border border-blue-200 dark:border-blue-700/50">
        <button
          type="button"
          onClick={() => setIsSchemeRegistryExpanded(v => !v)}
          className="w-full flex items-center justify-between px-6 py-3"
        >
          <div className="flex items-center gap-3">
            <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">Scheme Registry</span>
            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 rounded-full">
              {savedSchemes.length} scheme{savedSchemes.length !== 1 ? 's' : ''}
            </span>
          </div>
          <span className={`transition-transform ${isSchemeRegistryExpanded ? 'rotate-180' : ''}`}>
            <ChevronDown className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          </span>
        </button>
        
        {isSchemeRegistryExpanded && (
          <div className="px-6 pb-4">
            {isLoadingSchemes ? (
              <div className="flex items-center justify-center py-6">
                <Loader className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
                <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">Loading schemes...</span>
              </div>
            ) : savedSchemes.length === 0 ? (
              <div className="py-6 text-center">
                <Database className="h-10 w-10 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                <p className="text-sm text-gray-500 dark:text-gray-400">No segmentation schemes saved yet.</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  Create a scheme below and click "Add to Data" to save it here.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-white/50 dark:bg-gray-800/50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">Column Name</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">Method</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">Variables</th>
                      <th className="px-3 py-2 text-center font-medium text-gray-700 dark:text-gray-300">Segments</th>
                      <th className="px-3 py-2 text-center font-medium text-gray-700 dark:text-gray-300">IV</th>
                      <th className="px-3 py-2 text-center font-medium text-gray-700 dark:text-gray-300">Quality</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">Created</th>
                      <th className="px-3 py-2 text-center font-medium text-gray-700 dark:text-gray-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {savedSchemes.map((scheme, idx) => {
                      const modeLabels: Record<string, string> = {
                        'pre_existing': 'C1 - Pre-existing',
                        'variable_driven': 'C2 - Variable-Driven',
                        'manual_rules': 'C3 - Manual Rules',
                        'auto': 'Auto'
                      };
                      const qualityColors: Record<string, string> = {
                        'strong': 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400',
                        'moderate': 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400',
                        'acceptable': 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400',
                        'weak': 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400',
                        'useless': 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                      };
                      
                      return (
                        <tr key={scheme.scheme_id || idx} className="hover:bg-white/80 dark:hover:bg-gray-700/50 transition-colors">
                          <td className="px-3 py-2">
                            <code className="text-xs font-mono bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-800 dark:text-gray-200">
                              {scheme.column_name}
                            </code>
                          </td>
                          <td className="px-3 py-2 text-gray-700 dark:text-gray-300">
                            {modeLabels[scheme.mode] || scheme.mode}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1 max-w-[200px]">
                              {(scheme.variables || []).slice(0, 3).map((v: string, i: number) => (
                                <span key={i} className="px-1.5 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded truncate max-w-[80px]" title={v}>
                                  {v}
                                </span>
                              ))}
                              {(scheme.variables || []).length > 3 && (
                                <span className="px-1.5 py-0.5 text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-400 rounded">
                                  +{scheme.variables.length - 3}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-center font-medium text-gray-900 dark:text-gray-100">
                            {scheme.segment_count}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className="font-mono text-sm text-gray-900 dark:text-gray-100">
                              {formatSegmentationTotalIv(scheme.total_iv)}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${qualityColors[scheme.recommendation_category] || qualityColors['weak']}`}>
                              {scheme.recommendation_category?.charAt(0).toUpperCase() + scheme.recommendation_category?.slice(1) || 'Unknown'}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400">
                            {scheme.created_at ? new Date(scheme.created_at).toLocaleDateString('en-US', { 
                              month: 'short', 
                              day: 'numeric', 
                              hour: '2-digit', 
                              minute: '2-digit' 
                            }) : 'N/A'}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <button
                              type="button"
                              onClick={() => handleViewSchemeDetails(scheme)}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
                            >
                              <Info className="h-3 w-3" />
                              Details
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            
            {savedSchemes.length > 0 && (
              <div className="mt-3 pt-3 border-t border-blue-200 dark:border-blue-700/50">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  <Info className="h-3 w-3 inline mr-1" />
                  Schemes are saved as columns in your dataset. Use these during Model Training for segment-specific modeling.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Scheme Details Modal */}
      {isSchemeDetailsModalOpen && selectedSchemeDetails && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Scheme Details: {selectedSchemeDetails.column_name}
              </h3>
              <button
                type="button"
                onClick={() => setIsSchemeDetailsModalOpen(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            
            <div className="p-4 space-y-4">
              {isLoadingSchemeDetails && (
                <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                  <Loader className="h-4 w-4 animate-spin" />
                  Loading full audit metadata…
                </div>
              )}
              {selectedSchemeDetails._detailMessage && (
                <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-sm text-amber-800 dark:text-amber-200">
                  {selectedSchemeDetails._detailMessage}
                </div>
              )}
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Scheme ID</div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">#{selectedSchemeDetails.scheme_id}</div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Method</div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">
                    {{
                      'pre_existing': 'C1 - Pre-existing Identifier',
                      'variable_driven': 'C2 - Variable-Driven',
                      'manual_rules': 'C3 - Manual Rules',
                      'auto': 'Auto Segmentation'
                    }[selectedSchemeDetails.mode] || selectedSchemeDetails.mode}
                  </div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Segments</div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">{selectedSchemeDetails.segment_count}</div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total IV</div>
                  <div className="font-medium text-gray-900 dark:text-gray-100">{formatSegmentationTotalIv(selectedSchemeDetails.total_iv)}</div>
                </div>
              </div>
              
              {/* Variables */}
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Variables Used</div>
                <div className="flex flex-wrap gap-2">
                  {(selectedSchemeDetails.variables || []).map((v: string, i: number) => (
                    <span key={i} className="px-2 py-1 text-sm bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-200 rounded border border-gray-200 dark:border-gray-500">
                      {v}
                    </span>
                  ))}
                  {(!selectedSchemeDetails.variables || selectedSchemeDetails.variables.length === 0) && (
                    <span className="text-sm text-gray-500 dark:text-gray-400">No variables recorded</span>
                  )}
                </div>
              </div>
              
              {/* Variable Priority (if available) */}
              {selectedSchemeDetails.variable_priority && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Variable Priority</div>
                  <div className="space-y-1">
                    {selectedSchemeDetails.variable_priority.primary && (
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">1°</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{selectedSchemeDetails.variable_priority.primary}</span>
                      </div>
                    )}
                    {selectedSchemeDetails.variable_priority.secondary && (
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded">2°</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{selectedSchemeDetails.variable_priority.secondary}</span>
                      </div>
                    )}
                    {selectedSchemeDetails.variable_priority.tertiary && (
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded">3°</span>
                        <span className="text-sm text-gray-800 dark:text-gray-200">{selectedSchemeDetails.variable_priority.tertiary}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Quality Assessment */}
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Quality Assessment</div>
                <div className="flex items-center gap-2">
                  {selectedSchemeDetails.recommendation_category === 'strong' && (
                    <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                  )}
                  {selectedSchemeDetails.recommendation_category === 'moderate' && (
                    <Info className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  )}
                  {selectedSchemeDetails.recommendation_category === 'weak' && (
                    <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  )}
                  <span className="text-sm text-gray-800 dark:text-gray-200">
                    {selectedSchemeDetails.recommendation_category === 'strong' && 'Strong discriminatory power - Recommended for production use'}
                    {selectedSchemeDetails.recommendation_category === 'moderate' && 'Moderate discriminatory power - Acceptable with monitoring'}
                    {selectedSchemeDetails.recommendation_category === 'weak' && 'Weak discriminatory power - Consider alternative segmentation'}
                    {!['strong', 'moderate', 'weak'].includes(selectedSchemeDetails.recommendation_category) && 
                      `Quality: ${selectedSchemeDetails.recommendation_category || 'Unknown'}`}
                  </span>
                </div>
              </div>
              
              {/* Timestamp */}
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Created</div>
                <div className="text-sm text-gray-800 dark:text-gray-200">
                  {selectedSchemeDetails.created_at 
                    ? new Date(selectedSchemeDetails.created_at).toLocaleString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })
                    : 'Unknown'}
                </div>
              </div>

              {(selectedSchemeDetails.tree_method || selectedSchemeDetails.variable_selection_method) && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-1">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Method details</div>
                  {selectedSchemeDetails.tree_method && (
                    <div className="text-sm text-gray-800 dark:text-gray-200">
                      Tree / method: <span className="font-mono">{selectedSchemeDetails.tree_method}</span>
                    </div>
                  )}
                  {selectedSchemeDetails.variable_selection_method && (
                    <div className="text-sm text-gray-800 dark:text-gray-200">
                      Variable selection: <span className="font-mono">{selectedSchemeDetails.variable_selection_method}</span>
                    </div>
                  )}
                  {(selectedSchemeDetails.chi_squared_p != null || selectedSchemeDetails.cramers_v != null) && (
                    <div className="text-sm text-gray-800 dark:text-gray-200 mt-1">
                      {selectedSchemeDetails.chi_squared_p != null && (
                        <span className="mr-3">χ² {formatSegmentationChiSquaredPLabel(selectedSchemeDetails.chi_squared_p)}</span>
                      )}
                      {selectedSchemeDetails.cramers_v != null && (
                        <span>Cramer V: {Number(selectedSchemeDetails.cramers_v).toFixed(3)}</span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {Array.isArray(selectedSchemeDetails.merge_history) && selectedSchemeDetails.merge_history.length > 0 && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Merge history</div>
                  <ul className="list-disc list-inside text-sm text-gray-800 dark:text-gray-200 space-y-1">
                    {selectedSchemeDetails.merge_history.map((line: string, i: number) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}

              {Array.isArray(selectedSchemeDetails.cutoff_edits) && selectedSchemeDetails.cutoff_edits.length > 0 && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Cutoff edits</div>
                  <ul className="list-disc list-inside text-sm text-gray-800 dark:text-gray-200 space-y-1">
                    {selectedSchemeDetails.cutoff_edits.map((line: string, i: number) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedSchemeDetails.stability && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Bootstrap stability</div>
                  <pre className="text-xs overflow-x-auto text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                    {JSON.stringify(selectedSchemeDetails.stability, null, 2)}
                  </pre>
                </div>
              )}

              {selectedSchemeDetails.holdout_validation && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Holdout / OOS validation</div>
                  <pre className="text-xs overflow-x-auto text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                    {JSON.stringify(selectedSchemeDetails.holdout_validation, null, 2)}
                  </pre>
                </div>
              )}

              {schemeDetailRawJson && (
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Stored metadata (JSON)</div>
                  <pre className="text-xs max-h-64 overflow-auto text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono border border-gray-200 dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-900">
                    {schemeDetailRawJson}
                  </pre>
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                type="button"
                onClick={() => setIsSchemeDetailsModalOpen(false)}
                className="px-4 py-2 text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dataset Preview Section - Collapsible */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={() => setIsPreviewOpen(v => !v)}
          className="w-full flex items-center justify-between px-6 py-4"
        >
          <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dataset Preview</span>
          <span className={`transition-transform ${isPreviewOpen ? 'rotate-180' : ''}`}>
            <ChevronDown className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          </span>
        </button>
        {isPreviewOpen && (
          <div className="px-6 pb-6">
            {datasetPreview ? (
              <>
                <div className="mb-4">
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Dataset Shape: {datasetPreview.shape?.rows} rows × {datasetPreview.shape?.columns} columns
                  </p>
                </div>
                {datasetPreview.preview_data && (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-gray-700/50">
                        <tr>
                          {datasetPreview.preview_data.columns.map((column: string, index: number) => (
                            <th key={index} className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {datasetPreview.preview_data.rows.map((row: any, rowIndex: number) => (
                          <tr key={rowIndex}>
                            {datasetPreview.preview_data.columns.map((column: string, colIndex: number) => (
                              <td key={colIndex} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                                {row[column] !== null && row[column] !== undefined ? String(row[column]) : 'N/A'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <p>Loading dataset preview...</p>
              </div>
            )}
          </div>
        )}
      </div>


      {/* Segmentation Agent - 4-Mode Architecture */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Segmentation Agent</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Create meaningful segments to analyze your data. Choose a segmentation mode below.
          </p>
        </div>
        
        {/* 4-Mode Selection Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {segmentationModes.map(({ mode, label, shortLabel, description, icon: Icon, color }) => {
            const isSelected = agentMode === mode;
            const colorClassesMap: Record<string, { selected: string; icon: string; badge: string }> = {
              blue: {
                selected: 'border-blue-500 bg-blue-50 dark:bg-blue-900/30',
                icon: 'text-blue-600 dark:text-blue-400',
                badge: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
              },
              purple: {
                selected: 'border-purple-500 bg-purple-50 dark:bg-purple-900/30',
                icon: 'text-purple-600 dark:text-purple-400',
                badge: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300'
              },
              green: {
                selected: 'border-green-500 bg-green-50 dark:bg-green-900/30',
                icon: 'text-green-600 dark:text-green-400',
                badge: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
              },
              amber: {
                selected: 'border-amber-500 bg-amber-50 dark:bg-amber-900/30',
                icon: 'text-amber-600 dark:text-amber-400',
                badge: 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300'
              }
            };
            const colorClasses = colorClassesMap[color] || colorClassesMap.blue;
            
            return (
              <button
                key={mode}
                type="button"
                onClick={() => setAgentMode(mode)}
                className={`relative p-4 rounded-lg border-2 transition-all text-left ${
                  isSelected
                    ? `${colorClasses.selected} ring-2 ring-offset-2 ring-${color}-500/50`
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-gray-800'
                }`}
              >
                <div className={`flex items-center mb-2 ${mode === 'auto' ? 'justify-between' : ''}`}>
                  <Icon className={`h-5 w-5 ${isSelected ? colorClasses.icon : 'text-gray-400 dark:text-gray-500'}`} />
                  {mode === 'auto' && (
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                      isSelected ? colorClasses.badge : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                    }`}>
                      {shortLabel}
                    </span>
                  )}
                </div>
                <h4 className={`text-sm font-medium mb-1 ${
                  isSelected ? 'text-gray-900 dark:text-gray-100' : 'text-gray-700 dark:text-gray-300'
                }`}>
                  {label}
                </h4>
                <p className={`text-xs leading-relaxed ${
                  isSelected ? 'text-gray-600 dark:text-gray-400' : 'text-gray-500 dark:text-gray-500'
                }`}>
                  {description}
                </p>
                {isSelected && (
                  <div className={`absolute top-2 right-2`}>
                    <CheckCircle2 className={`h-4 w-4 ${colorClasses.icon}`} />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Mode-specific description */}
        <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {segmentationModes.find(m => m.mode === agentMode)?.description}
            </p>
          </div>
        </div>

        {/* =================================================================== */}
        {/* MODE-SPECIFIC CONTROLS */}
        {/* =================================================================== */}

        {/* C1: Pre-existing Identifier Mode */}
        {agentMode === 'pre_existing' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Select Segment Column
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Choose an existing column that contains segment identifiers. Only <strong className="text-gray-700 dark:text-gray-300">categorical</strong> columns or columns with at most {PRE_EXISTING_MAX_CARDINALITY} distinct values are listed (per dataset analysis).
              </p>
              <select
                value={selectedSegmentColumn}
                onChange={(e) => setSelectedSegmentColumn(e.target.value)}
                disabled={preExistingIdentifierOptions.length === 0}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
              >
                <option value="">
                  {preExistingIdentifierOptions.length === 0
                    ? '-- No eligible columns (complete dataset analysis or use a categorical / low-cardinality field) --'
                    : '-- Select a column --'}
                </option>
                {preExistingIdentifierOptions.map((col) => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
              {selectedSegmentColumn && (
                <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <span className="text-sm text-blue-800 dark:text-blue-300">
                      Column "{selectedSegmentColumn}" selected as segment identifier
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* C2: Variable-Driven Mode */}
        {agentMode === 'variable_driven' && (
          <div className="space-y-4">
            {/* Variable Priority Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Variable Priority
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Select variables in order of importance. Primary variable will be used for the root split.
              </p>
              
              <div className="space-y-3">
                {/* Primary Variable */}
                <div className="flex items-center gap-3">
                  <span className="w-20 text-xs font-semibold text-purple-600 dark:text-purple-400 bg-purple-100 dark:bg-purple-900/30 px-2 py-1 rounded">Primary</span>
                  <select
                    value={variablePriority.primary}
                    onChange={(e) => setVariablePriority(prev => ({ ...prev, primary: e.target.value }))}
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="">-- Select primary variable --</option>
                    {availableColumns
                      .filter(c => c !== variablePriority.secondary && c !== variablePriority.tertiary)
                      .map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                  </select>
                </div>
                
                {/* Secondary Variable */}
                <div className="flex items-center gap-3">
                  <span className="w-20 text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-100 dark:bg-indigo-900/30 px-2 py-1 rounded">Secondary</span>
                  <select
                    value={variablePriority.secondary || ''}
                    onChange={(e) => setVariablePriority(prev => ({ ...prev, secondary: e.target.value || null }))}
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500"
                    disabled={!variablePriority.primary}
                  >
                    <option value="">-- Optional --</option>
                    {availableColumns
                      .filter(c => c !== variablePriority.primary && c !== variablePriority.tertiary)
                      .map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                  </select>
                </div>
                
                {/* Tertiary Variable */}
                <div className="flex items-center gap-3">
                  <span className="w-20 text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 px-2 py-1 rounded">Tertiary</span>
                  <select
                    value={variablePriority.tertiary || ''}
                    onChange={(e) => setVariablePriority(prev => ({ ...prev, tertiary: e.target.value || null }))}
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500"
                    disabled={!variablePriority.secondary}
                  >
                    <option value="">-- Optional --</option>
                    {availableColumns
                      .filter(c => c !== variablePriority.primary && c !== variablePriority.secondary)
                      .map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                  </select>
                </div>
              </div>
            </div>
            
            {/* Method Selection */}
            <div className="flex items-center gap-4 pt-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Method:</label>
              <label className="flex items-center gap-2 text-sm dark:text-gray-300">
                <input type="radio" name="c2-method" value="cart" checked={segmentationMethod === 'cart'} onChange={() => setSegmentationMethod('cart')} />
                CART
              </label>
              <label
                className={`flex items-center gap-2 text-sm ${problemType === 'regression' ? 'text-gray-400' : 'dark:text-gray-300'}`}
              >
                <input type="radio" name="c2-method" value="chaid" checked={segmentationMethod === 'chaid'} onChange={() => setSegmentationMethod('chaid')} disabled={problemType === 'regression'} />
                CHAID
              </label>
            </div>
            
            {/* Segmentation Constraints */}
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Min Segment Size</label>
                <input
                  type="number"
                  value={minSegmentSize}
                  onChange={(e) => setMinSegmentSize(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Segments</label>
                <input
                  type="number"
                  value={maxSegments}
                  onChange={(e) => setMaxSegments(parseInt(e.target.value) || 2)}
                  min={2}
                  max={20}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* C3: Manual Rules Mode — configure + segment cards (plan §6) */}
        {agentMode === 'manual_rules' && (
          <div className="space-y-6">
            {/* Configure header */}
            <div className="rounded-xl border border-slate-200/80 dark:border-slate-600/80 bg-gradient-to-br from-white to-slate-50/80 dark:from-slate-900 dark:to-slate-900/70 px-5 py-4 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-950/50 text-orange-600 dark:text-orange-400">
                  <Settings className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 tracking-tight">
                    Configure segment rules
                  </h3>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                    Define each segment with SQL-style conditions. Segments are evaluated top to bottom; the first
                    matching segment wins.
                  </p>
                </div>
              </div>
            </div>

            {/* Segment definitions */}
            <div>
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    Segment definitions
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-0.5">
                    Drag cards to reorder priority. First matching segment wins.
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                {manualRules.map((rule, ruleIndex) => {
                  const isRangeOp = (op: string) => ['between', 'not_between'].includes(String(op).toLowerCase());
                  const countBadge =
                    ruleValidationResult?.segment_counts &&
                    typeof ruleValidationResult.segment_counts[rule.segment_name] === 'number'
                      ? ruleValidationResult.segment_counts[rule.segment_name]
                      : null;
                  return (
                    <div
                      key={ruleIndex}
                      draggable
                      onDragStart={() => setDragRuleIndex(ruleIndex)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => {
                        if (dragRuleIndex !== null) moveRule(dragRuleIndex, ruleIndex);
                        setDragRuleIndex(null);
                      }}
                      className="overflow-hidden rounded-xl border border-slate-200/90 dark:border-slate-600 bg-white dark:bg-slate-900/50 shadow-sm ring-1 ring-slate-900/5 dark:ring-white/5 transition-shadow hover:shadow-md"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-700/80 bg-slate-50/60 dark:bg-slate-800/40 px-4 py-3">
                        <div className="flex min-w-0 flex-1 items-center gap-3">
                          <span title="Drag to reorder" className="shrink-0 cursor-grab text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                            <GripVertical className="h-5 w-5" />
                          </span>
                          <input
                            type="text"
                            value={rule.segment_name}
                            onChange={(e) => updateSegmentRule(ruleIndex, { segment_name: e.target.value })}
                            title="Click to rename this segment"
                            aria-label="Segment name (editable)"
                            autoComplete="off"
                            spellCheck={false}
                            className="min-w-[8rem] max-w-md flex-1 cursor-text rounded-md border border-slate-200/90 bg-white px-2.5 py-1 text-sm font-semibold text-slate-900 shadow-sm transition placeholder:text-slate-400 hover:border-slate-300 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-200/70 dark:border-slate-500 dark:bg-slate-800/50 dark:text-slate-100 dark:placeholder:text-slate-500 dark:hover:border-slate-400 dark:focus:border-orange-500 dark:focus:ring-orange-900/50"
                            placeholder="Segment name"
                          />
                          {countBadge !== null && (
                            <span className="shrink-0 rounded-full bg-sky-100 dark:bg-sky-950/60 px-3 py-1 text-xs font-medium tabular-nums text-sky-900 dark:text-sky-100">
                              {countBadge.toLocaleString()} records
                            </span>
                          )}
                          {rule.catch_all && (
                            <span className="shrink-0 rounded-full bg-emerald-100 dark:bg-emerald-900/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-200">
                              Catch-all
                            </span>
                          )}
                        </div>
                        {manualRules.length > 1 && (
                          <div className="flex shrink-0 items-center">
                            <button
                              type="button"
                              onClick={() => removeSegmentRule(ruleIndex)}
                              className="rounded-lg p-2 text-rose-500 transition-colors hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40"
                              aria-label="Remove segment"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="px-4 py-4">
                        {rule.catch_all && rule.conditions.length === 0 && (
                          <p className="mb-4 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                            Assigns every row not matched by segments above. Add optional conditions to narrow within
                            unassigned rows.
                          </p>
                        )}

                        <div className="space-y-3">
                          {rule.conditions.map((condition, condIndex) => {
                            const range = isRangeOp(condition.operator);
                            let lo = '';
                            let hi = '';
                            if (range) {
                              const v = condition.value as string | number[] | undefined;
                              if (Array.isArray(v) && v.length >= 2) {
                                lo = String(v[0]);
                                hi = String(v[1]);
                              } else if (typeof v === 'string' && v.includes(',')) {
                                const p = v.split(',').map((s) => s.trim());
                                lo = p[0] || '';
                                hi = p[1] || '';
                              }
                            }
                            const valStr = String(condition.value ?? '');
                            return (
                              <React.Fragment key={condIndex}>
                                {condIndex > 0 && (
                                  <div
                                    className="flex w-full items-center justify-center gap-2 py-1.5"
                                    role="group"
                                    aria-label="How to combine with the previous condition"
                                  >
                                    <div className="h-px flex-1 max-w-[40%] bg-slate-200/90 dark:bg-slate-600/80" />
                                    <select
                                      value={rule.logic}
                                      onChange={(e) => updateSegmentRule(ruleIndex, { logic: e.target.value as 'AND' | 'OR' })}
                                      className="shrink-0 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-700 dark:text-slate-200 shadow-sm"
                                    >
                                      <option value="AND">AND</option>
                                      <option value="OR">OR</option>
                                    </select>
                                    <div className="h-px flex-1 max-w-[40%] bg-slate-200/90 dark:bg-slate-600/80" />
                                  </div>
                                )}
                              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                                <span className="w-14 shrink-0 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 sm:pt-2.5">
                                  Where
                                </span>
                                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                                  <select
                                    value={condition.variable}
                                    onChange={(e) => updateCondition(ruleIndex, condIndex, { variable: e.target.value })}
                                    className="min-w-[9rem] flex-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-800 dark:text-slate-100 shadow-sm focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-200/50 dark:focus:ring-orange-900/40"
                                  >
                                    <option value="">Select variable</option>
                                    {availableColumns.map((col) => (
                                      <option key={col} value={col}>
                                        {col}
                                      </option>
                                    ))}
                                  </select>
                                  <select
                                    value={condition.operator}
                                    onChange={(e) => updateCondition(ruleIndex, condIndex, { operator: e.target.value })}
                                    className="min-w-[9rem] rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-800 dark:text-slate-100 shadow-sm focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-200/50 dark:focus:ring-orange-900/40"
                                  >
                                    {operatorOptions.map((op) => (
                                      <option key={op.value} value={op.value}>
                                        {op.label}
                                      </option>
                                    ))}
                                  </select>
                                  {range ? (
                                    <div className="flex min-w-[12rem] flex-1 items-center gap-2">
                                      <input
                                        type="text"
                                        value={lo}
                                        onChange={(e) => updateCondition(ruleIndex, condIndex, { value: `${e.target.value},${hi}` })}
                                        placeholder="Low"
                                        className="w-full min-w-0 flex-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm shadow-sm"
                                      />
                                      <span className="text-xs font-medium text-slate-400">and</span>
                                      <input
                                        type="text"
                                        value={hi}
                                        onChange={(e) => updateCondition(ruleIndex, condIndex, { value: `${lo},${e.target.value}` })}
                                        placeholder="High"
                                        className="w-full min-w-0 flex-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm shadow-sm"
                                      />
                                    </div>
                                  ) : !['is_null', 'is_not_null', 'is_true', 'is_false'].includes(condition.operator) ? (
                                    <div className="relative flex min-w-[8rem] flex-1">
                                      <input
                                        type="text"
                                        value={(condition.value ?? '') as string | number}
                                        onChange={(e) => updateCondition(ruleIndex, condIndex, { value: e.target.value })}
                                        placeholder={
                                          ['in', 'not_in'].includes(condition.operator)
                                            ? "e.g. 'A', 'B' or comma-separated"
                                            : 'Value'
                                        }
                                        className="w-full rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 py-2 pl-3 pr-8 text-sm shadow-sm"
                                      />
                                      {valStr !== '' && (
                                        <button
                                          type="button"
                                          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                                          onClick={() => updateCondition(ruleIndex, condIndex, { value: '' })}
                                          aria-label="Clear value"
                                        >
                                          <X className="h-3.5 w-3.5" />
                                        </button>
                                      )}
                                    </div>
                                  ) : null}
                                  <div className="flex items-center gap-1">
                                    {rule.conditions.length > 1 && (
                                      <button
                                        type="button"
                                        onClick={() => removeCondition(ruleIndex, condIndex)}
                                        className="rounded-lg p-2 text-rose-500 transition-colors hover:bg-rose-50 dark:hover:bg-rose-950/30"
                                        title="Remove condition"
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </button>
                                    )}
                                  </div>
                                </div>
                              </div>
                              </React.Fragment>
                            );
                          })}
                        </div>

                        <button
                          type="button"
                          onClick={() => addCondition(ruleIndex)}
                          className="mt-3 text-xs font-semibold text-orange-600 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300"
                        >
                          + Add condition
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Actions + status bar */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={addSegmentRule}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Plus className="h-4 w-4 text-slate-500" />
                Add segment
              </button>
              <button
                type="button"
                onClick={addCatchAllSegment}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <ListPlus className="h-4 w-4 text-slate-500" />
                Add catch-all
              </button>
            </div>

            {ruleValidationResult && (
              <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900/40 shadow-sm">
                <div className="h-2.5 w-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className="h-full rounded-r-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, ruleValidationResult.coverage_pct))}%` }}
                  />
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm">
                  <span className="font-semibold text-slate-800 dark:text-slate-100">
                    {ruleValidationResult.coverage_pct.toFixed(0)}% coverage
                  </span>
                  {ruleValidationResult.is_mutually_exclusive ? (
                    <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="h-4 w-4" />
                      Mutually exclusive
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 font-medium text-amber-600 dark:text-amber-400">
                      <AlertTriangle className="h-4 w-4" />
                      Overlap detected
                    </span>
                  )}
                  <span className="text-slate-500 dark:text-slate-400">
                    {manualRules.length} segment{manualRules.length === 1 ? '' : 's'} defined
                  </span>
                  {ruleValidationResult.unassigned_records > 0 && (
                    <span className="text-amber-700 dark:text-amber-300">
                      {ruleValidationResult.unassigned_records.toLocaleString()} unassigned
                    </span>
                  )}
                </div>
                {ruleValidationResult.unassigned_records > 0 && !manualRules.some((r) => r.catch_all) && (
                  <div className="border-t border-slate-100 dark:border-slate-700 px-4 pb-3">
                    <button
                      type="button"
                      onClick={addCatchAllSegment}
                      className="text-xs font-semibold text-orange-600 hover:text-orange-700 dark:text-orange-400"
                    >
                      Add catch-all for orphan rows?
                    </button>
                  </div>
                )}
                {ruleValidationResult.empty_segments.length > 0 && (
                  <div className="border-t border-amber-100 bg-amber-50/50 px-4 py-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                    Empty segments: {ruleValidationResult.empty_segments.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Auto Segmentation Mode */}
        {agentMode === 'auto' && (
          <div className="space-y-4">
            {/* Auto Candidates Display - Enhanced with Quality Composite metrics */}
            {autoCandidates.length > 0 && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Discovered Schemes (Quality Composite Ranked)
                </label>
                {autoCandidates.map((candidate, idx) => (
                  <div 
                    key={idx} 
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedAutoScheme === idx
                        ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/30'
                        : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                    }`}
                    onClick={() => setSelectedAutoScheme(idx)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Scheme {idx + 1}: {candidate.variables?.join(' → ')}
                      </span>
                      <div className="flex items-center gap-2">
                        {candidate.recommended && (
                          <span className="text-xs font-semibold px-2 py-0.5 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded">
                            RECOMMENDED
                          </span>
                        )}
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                          candidate.recommendation_category === 'strong' 
                            ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                            : candidate.recommendation_category === 'exploratory'
                            ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300'
                            : 'bg-gray-100 dark:bg-gray-900/50 text-gray-700 dark:text-gray-300'
                        }`}>
                          {candidate.recommendation_category?.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    
                    {/* Quality Composite metrics */}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs text-gray-500 dark:text-gray-400">
                      <span>Total IV: {candidate.iv?.toFixed(4)}</span>
                      <span>Segments: {candidate.num_segments} (from {candidate.original_segments || 'N/A'})</span>
                      <span>Balance: {(candidate.segment_balance * 100)?.toFixed(1)}%</span>
                      <span>Spread: {candidate.event_rate_spread?.toFixed(2)}pp</span>
                      <span>Method: {candidate.method?.toUpperCase()}</span>
                      <span className="font-semibold text-amber-600 dark:text-amber-400">
                        Score: {candidate.score?.toFixed(1)}
                      </span>
                    </div>
                    
                    {/* Show merge/constraint trail on hover or click */}
                    {selectedAutoScheme === idx && (candidate.merge_trail?.length > 0 || candidate.constraint_trail?.length > 0 || candidate.splitter_selection_trail?.length > 0) && (
                      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 space-y-1">
                        {candidate.splitter_selection_trail?.length > 0 && (
                          <div className="text-xs text-blue-500 dark:text-blue-400">
                            <span className="font-medium">Selection:</span> {candidate.splitter_selection_trail.slice(0, 3).join(' → ')}
                            {candidate.splitter_selection_trail.length > 3 && ` (+${candidate.splitter_selection_trail.length - 3} more)`}
                          </div>
                        )}
                        {candidate.merge_trail?.length > 0 && (
                          <div className="text-xs text-gray-400 dark:text-gray-500">
                            <span className="font-medium">Merges:</span> {candidate.merge_trail.slice(0, 3).join('; ')}
                            {candidate.merge_trail.length > 3 && ` (+${candidate.merge_trail.length - 3} more)`}
                          </div>
                        )}
                        {candidate.constraint_trail?.length > 0 && (
                          <div className="text-xs text-gray-400 dark:text-gray-500">
                            <span className="font-medium">Constraints:</span> {candidate.constraint_trail.slice(0, 2).join('; ')}
                            {candidate.constraint_trail.length > 2 && ` (+${candidate.constraint_trail.length - 2} more)`}
                          </div>
                        )}
                        
                        {/* Show promotion suggestion if present */}
                        {candidate.promotion_suggestion && (
                          <div className={`text-xs p-2 rounded mt-2 ${
                            candidate.promotion_suggestion.type === 'promote_tertiary'
                              ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300 border border-yellow-200 dark:border-yellow-800'
                              : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                          }`}>
                            <span className="font-medium">
                              {candidate.promotion_suggestion.type === 'promote_tertiary' ? '💡 Suggestion: ' : 'ℹ️ Note: '}
                            </span>
                            {candidate.promotion_suggestion.message}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Promotion Suggestions — Section 3.4 (C2 tertiary promotion + auto pipeline) */}
        {promotionSuggestions.length > 0 && (
          <div className="mt-4 space-y-2">
            {promotionSuggestions.map((suggestion: any, idx: number) => {
              const kind = suggestion.suggestion_type || suggestion.type;
              const isPromote = kind === 'promote_tertiary';
              return (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${
                  isPromote
                    ? 'bg-amber-50 dark:bg-amber-900/25 border-amber-300 dark:border-amber-700'
                    : 'bg-amber-50/60 dark:bg-amber-900/15 border-amber-200 dark:border-amber-800'
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg">
                    {isPromote ? '💡' : 'ℹ️'}
                  </span>
                  <div className="flex-1">
                    <p
                      className={`text-sm font-medium ${
                        isPromote
                          ? 'text-amber-900 dark:text-amber-100'
                          : 'text-amber-800 dark:text-amber-200'
                      }`}
                    >
                      {suggestion.message}
                    </p>

                    {suggestion.suggested_variable && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-gray-600 dark:text-gray-400">
                          Suggested: <strong>{suggestion.suggested_variable}</strong>
                          {suggestion.suggested_p_value != null &&
                            ` (p = ${Number(suggestion.suggested_p_value).toFixed(4)})`}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
            })}
          </div>
        )}

        {/* =================================================================== */}
        {/* ERROR DISPLAY */}
        {/* =================================================================== */}
        {segmentationError && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium text-red-800 dark:text-red-200">
                  Segmentation Error
                </h4>
                <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                  {segmentationError}
                </p>
                {segmentationError.includes('timed out') && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-2">
                    Tip: Try reducing the number of segments or selecting fewer variables.
                  </p>
                )}
                {segmentationError.includes('Unable to connect') && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-2">
                    Please ensure the backend server is running and try again.
                  </p>
                )}
              </div>
              <button
                onClick={() => setSegmentationError(null)}
                className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* UNIFIED RUN BUTTON */}
        {/* =================================================================== */}
        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={handleRunUnifiedSegmentation}
            disabled={
              isRunningUnifiedSegmentation ||
              (agentMode === 'pre_existing' && !selectedSegmentColumn) ||
              (agentMode === 'variable_driven' && !variablePriority.primary)
            }
            className={`w-full px-4 py-3 rounded-xl font-semibold shadow-md transition-all flex items-center justify-center gap-2 ${
              agentMode === 'pre_existing'
                ? 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600'
                : agentMode === 'variable_driven'
                  ? 'bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-600'
                  : agentMode === 'manual_rules'
                    ? 'bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 dark:from-orange-600 dark:to-orange-700'
                    : 'bg-amber-600 hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-600'
            } text-white disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed disabled:shadow-none`}
          >
            {isRunningUnifiedSegmentation ? (
              <>
                <Loader className="h-5 w-5 animate-spin" />
                <span>Running Segmentation...</span>
              </>
            ) : (
              <>
                <ArrowRight className="h-5 w-5" />
                <span>Run Segmentation</span>
              </>
            )}
          </button>
        </div>

        {/* Segmentation Result Warning */}
        {segmentationResult?.warning && (
          <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/40 rounded-lg">
            <div className="flex items-start">
              <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">Segmentation Warning</p>
                <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">{segmentationResult.warning}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Segmented Dataset Preview Section - Collapsible */}
      {segmentedDatasetPreview && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <ChevronDown 
                className={`h-5 w-5 text-gray-500 dark:text-gray-400 transition-transform ${isSegmentedPreviewOpen ? 'rotate-180' : ''}`}
              />
              <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">Segmented Dataset Preview</span>
            </div>
            <button
              onClick={() => setIsSegmentedPreviewOpen(!isSegmentedPreviewOpen)}
              className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
            >
              {isSegmentedPreviewOpen ? 'Hide' : 'Show'}
            </button>
          </div>
          
          {isSegmentedPreviewOpen && (
            <div className="mt-4">
              {isLoadingSegmentedPreview ? (
                <div className="flex flex-col items-center justify-center py-12 space-y-3">
                  <Loader className="h-8 w-8 text-blue-600 animate-spin" />
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Updating dataset preview...</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Loading latest segmented data</p>
                </div>
              ) : segmentedDatasetPreview ? (
                <>
                  <div className="mb-4">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Segmented Dataset Shape: {segmentedDatasetPreview.shape?.rows} rows × {segmentedDatasetPreview.shape?.columns} columns
                    </p>
                  </div>
                  {segmentedDatasetPreview.preview_data && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-50 dark:bg-gray-700/50">
                          <tr>
                            {segmentedDatasetPreview.preview_data.columns.map((column: string, index: number) => (
                              <th key={index} className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                          {segmentedDatasetPreview.preview_data.rows.map((row: any, rowIndex: number) => (
                            <tr key={rowIndex}>
                              {segmentedDatasetPreview.preview_data.columns.map((column: string, colIndex: number) => (
                                <td key={colIndex} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                                  {row[column] !== null && row[column] !== undefined ? String(row[column]) : 'N/A'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <p>Loading segmented dataset preview...</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Chat Component */}
      {renderStepChat(3.5)}

    </div>
  );
};

export default Step3_5SegmentationAgentAnalysis;