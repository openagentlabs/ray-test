import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';
import { FastAPIService, ColumnInfo, FeatureTransformationRequest, FeatureTransformationResponse, fastApiService } from '../../services/fastApiService';
import UserKnowledgeUploadPanel from '../UserKnowledgeUploadPanel';
import DataSplit from '../DataSplit';

interface Step4FeatureEngineeringProps {
  // Feature engineering functionality states
  selectedFeatureSteps: string[];
  setSelectedFeatureSteps: (steps: string[]) => void;
  
  // Feature engineering handlers (removed as we now use direct API calls)
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
  
  // Dataset information
  datasetId?: string;
  targetVariable?: string;
  activeDatasetId?: string | null;
  
  // Segmentation constraints from previous step
  maxSegments?: number;
  segmentationResult?: any; // Segmentation result with segment rules
}

// No mock data - only real data from API

const Step4FeatureEngineering: React.FC<Step4FeatureEngineeringProps> = ({
  selectedFeatureSteps,
  setSelectedFeatureSteps,
  renderStepChat,
  datasetId,
  targetVariable,
  activeDatasetId,
  maxSegments,
  segmentationResult
}) => {
  // New state for Screen2 - with sessionStorage persistence
  const [showVariableSelection, setShowVariableSelection] = useState(false);
  const [selectedTransformation, setSelectedTransformation] = useState(
    typeof window !== 'undefined' 
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_selected_transformation');
          return saved || '';
        })()
      : ''
  );
  const [selectedVariables, setSelectedVariables] = useState<string[]>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_selected_variables');
          return saved ? JSON.parse(saved) : [];
        })()
      : []
  );
  
  // State to track all applied transformations - with sessionStorage persistence
  const [appliedTransformations, setAppliedTransformations] = useState<Record<string, string>>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_applied_transformations');
          return saved ? JSON.parse(saved) : {};
        })()
      : {}
  );
  
  // New state for Screen3 - with sessionStorage persistence
  const [showReviewScreen, setShowReviewScreen] = useState(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_show_review');
          return saved === 'true';
        })()
      : false
  );
  
  // New state for Screen4 - with sessionStorage persistence
  const [showFinalReport, setShowFinalReport] = useState(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_show_final_report');
          return saved === 'true';
        })()
      : false
  );
  
  // API response state - with sessionStorage persistence
  const [transformationResponse, setTransformationResponse] = useState<FeatureTransformationResponse | null>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_transformation_response');
          return saved ? JSON.parse(saved) : null;
        })()
      : null
  );
  const [isTransforming, setIsTransforming] = useState(false);
  const [transformJobId, setTransformJobId] = useState<string | null>(null);
  const [transformProgress, setTransformProgress] = useState<number>(0);
  const [transformStatusMessage, setTransformStatusMessage] = useState<string>('');
  
  // Code logic modal state
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [selectedCodeLogic, setSelectedCodeLogic] = useState<string>('');
  
  // State to remember last selected variables for each transformation - with sessionStorage persistence
  const [lastSelectedVariables, setLastSelectedVariables] = useState<Record<string, string[]>>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_last_selected_variables');
          return saved ? JSON.parse(saved) : {};
        })()
      : {}
  );
  
  // Enhanced modal flow state
  
  // Real data states
  const [realVariables, setRealVariables] = useState<ColumnInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  
  // Variable definitions states
  const [variableDefinitions, setVariableDefinitions] = useState<Record<string, string>>({});
  
  // Search functionality - with sessionStorage persistence
  const [searchQuery, setSearchQuery] = useState<string>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('feature_engineering_search_query');
          return saved || '';
        })()
      : ''
  );

  // Read Step 1 configuration to determine if split was selected AND applied
  const [useSplit, setUseSplit] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const cfgRaw = sessionStorage.getItem('dataset_config');
      if (cfgRaw) {
        try {
          const cfg = JSON.parse(cfgRaw);
          // Check if split_configuration exists (new Train/Test/Validation system)
          if (cfg.split_configuration) {
            return true;
          }
          // Fallback to old system
          if (cfg.initial_scope) {
            return cfg.initial_scope === 'split';
          }
          return cfg.data_scope === 'split' && cfg.initial_scope === 'split';
        } catch (e) {
          console.error('Error parsing dataset_config:', e);
        }
      }
    }
    return false; // Default to entire mode until split is applied
  });

  // Split ratios for Train/Test/Validation
  const [splitRatios, setSplitRatios] = useState<{ train: number; test: number; validation: number }>(() => {
    if (typeof window !== 'undefined') {
      const cfgRaw = sessionStorage.getItem('dataset_config');
      if (cfgRaw) {
        try {
          const cfg = JSON.parse(cfgRaw);
          // Read from new split_configuration.ratios
          if (cfg.split_configuration?.ratios) {
            return {
              train: cfg.split_configuration.ratios.train || 60,
              test: cfg.split_configuration.ratios.test || 20,
              validation: cfg.split_configuration.ratios.validation || 20
            };
          }
          // Fallback to old split_ratio (convert to new format)
          if (cfg.split_ratio !== undefined && cfg.split_ratio !== null) {
            const trainPercent = Math.round(cfg.split_ratio * 100);
            const remaining = 100 - trainPercent;
            return {
              train: trainPercent,
              test: Math.round(remaining / 2),
              validation: remaining - Math.round(remaining / 2)
            };
          }
        } catch (e) {
          console.error('Error parsing dataset_config:', e);
        }
      }
    }
    return { train: 60, test: 20, validation: 20 };
  });

  // Current active scope (train, test, or validation)
  const [activeScope, setActiveScope] = useState<'train' | 'test' | 'validation'>('train');

  // Listen for changes to Step 1 configuration and update split status
  useEffect(() => {
    const handleConfigChange = () => {
      if (typeof window !== 'undefined') {
        const cfgRaw = sessionStorage.getItem('dataset_config');
        if (cfgRaw) {
          try {
            const cfg = JSON.parse(cfgRaw);
            // Check for new split_configuration
            if (cfg.split_configuration) {
              setUseSplit(true);
              if (cfg.split_configuration.ratios) {
                setSplitRatios({
                  train: cfg.split_configuration.ratios.train || 60,
                  test: cfg.split_configuration.ratios.test || 20,
                  validation: cfg.split_configuration.ratios.validation || 20
                });
              }
            } else if (cfg.initial_scope) {
              setUseSplit(cfg.initial_scope === 'split');
            }
          } catch (e) {
            console.error('Error parsing dataset_config:', e);
          }
        }
      }
    };

    // Listen for custom event from Step 1 when config changes
    window.addEventListener('datasetConfigChanged', handleConfigChange);
    
    // Also check on component mount and when activeDatasetId changes
    handleConfigChange();

    return () => {
      window.removeEventListener('datasetConfigChanged', handleConfigChange);
    };
  }, [activeDatasetId]);

  // Automatically set scope to 'entire' when component mounts (Feature Engineering always uses entire dataset)
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
        console.error('Failed to set scope to entire in Feature Engineering:', error);
        // Don't show error to user, just log it
      }
    };
    
    setScopeToEntire();
  }, [activeDatasetId]);

  // Fetch real dataset variables
  const fetchDatasetVariables = async () => {
    if (!datasetId) {
      setError('No dataset ID available. Please upload a dataset first.');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const fastApiService = new FastAPIService();
      const response = await fastApiService.getColumnInfo(datasetId);
      
      if (response && response.columns_info) {
        setRealVariables(response.columns_info);
        setError(''); // Clear any previous errors
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      setError(`Failed to load dataset variables: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setRealVariables([]); // Clear variables on error
    } finally {
      setLoading(false);
    }
  };

  // Fetch variable definitions
  const fetchVariableDefinitions = async (columns: string[]) => {
    if (!datasetId || columns.length === 0) {
      return;
    }

    try {
      const fastApiService = new FastAPIService();
      const response = await fastApiService.getVariableDefinitions(datasetId, columns);
      
      if (response && response.definitions) {
        const definitions: Record<string, string> = {};
        Object.entries(response.definitions).forEach(([column, definition]) => {
          definitions[column] = definition.definition;
        });
        setVariableDefinitions(prev => ({ ...prev, ...definitions }));
      }
    } catch (err) {
      // Don't show error to user, just use fallback definitions
    }
  };


  // Load data on component mount
  useEffect(() => {
    fetchDatasetVariables();
  }, [datasetId]);

  // Fetch variable definitions when realVariables change
  useEffect(() => {
    if (realVariables.length > 0) {
      const columnNames = realVariables.map(v => v.column_name);
      fetchVariableDefinitions(columnNames);
    }
  }, [realVariables, datasetId]);

  // Save state to sessionStorage whenever it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_selected_transformation', selectedTransformation);
    }
  }, [selectedTransformation]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_selected_variables', JSON.stringify(selectedVariables));
    }
  }, [selectedVariables]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_applied_transformations', JSON.stringify(appliedTransformations));
    }
  }, [appliedTransformations]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_show_review', showReviewScreen.toString());
    }
  }, [showReviewScreen]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_show_final_report', showFinalReport.toString());
    }
  }, [showFinalReport]);

  useEffect(() => {
    if (typeof window !== 'undefined' && transformationResponse) {
      sessionStorage.setItem('feature_engineering_transformation_response', JSON.stringify(transformationResponse));
    }
  }, [transformationResponse]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_last_selected_variables', JSON.stringify(lastSelectedVariables));
    }
  }, [lastSelectedVariables]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('feature_engineering_search_query', searchQuery);
    }
  }, [searchQuery]);

  // Helper function to convert underscores to spaces for display
  const formatVariableName = (name: string) => {
    return name.replace(/_/g, ' ');
  };

  const isCategoricalColumn = (col: ColumnInfo) => {
    if (col.column_type === 'Categorical') return true;
    const dt = (col.data_type || '').toLowerCase();
    return dt.includes('object') || dt.includes('string') || dt.includes('category') || dt === 'bool' || dt === 'boolean';
  };

  // Helper function to format code logic for display
  const formatCodeLogic = (code: string) => {
    return code.replace(/_/g, ' ');
  };

  // Get transformation display name
  const getTransformationName = (step: string) => {
    switch (step) {
      case 'woe_transformation': return 'WOE Transformation';
      case 'log_transformation': return 'Log Transformation';
      case 'one_hot_encoding': return 'One Hot Encoding';
      default: return step;
    }
  };

  // Get meaningful variable definition - now uses API with fallback
  const getVariableDefinition = (columnName: string, dataType: string) => {
    // First try to get from API definitions
    if (variableDefinitions[columnName]) {
      return variableDefinitions[columnName];
    }
    
    // Fallback to generic patterns if API definition not available
    const name = columnName.toLowerCase();
    
    // Generic patterns
    if (name.includes('age')) return 'Age information';
    if (name.includes('income')) return 'Income amount';
    if (name.includes('score')) return 'Rating or score value';
    if (name.includes('amount')) return 'Monetary amount';
    if (name.includes('rate')) return 'Rate or percentage';
    if (name.includes('status')) return 'Current status';
    if (name.includes('type')) return 'Category or type';
    if (name.includes('date') || name.includes('_d')) return 'Date information';
    if (name.includes('count') || name.includes('num')) return 'Count or number';
    if (name.includes('flag')) return 'Binary flag indicator';
    if (name.includes('desc') || name.includes('description')) return 'Description text';
    if (name.includes('url')) return 'URL or web link';
    if (name.includes('term')) return 'Term or duration';
    if (name.includes('id')) return 'Identifier field';
    
    // Default based on data type
    if (dataType === 'object') return 'Categorical information';
    if (['int64', 'float64'].includes(dataType)) return 'Numerical measurement';
    if (dataType === 'bool') return 'True/False indicator';
    if (dataType.includes('datetime')) return 'Date and time information';
    
    return 'Data field';
  };

  // Handle Submit from Screen1
  const handleScreen1Submit = () => {
    const selectedStep = selectedFeatureSteps[0]; // Get first selected transformation
    if (selectedStep) {
      const transformationName = getTransformationName(selectedStep);
      setSelectedTransformation(transformationName);
      
      // Pre-select variables from last time if same transformation
      const lastVariables = lastSelectedVariables[transformationName] || [];
      setSelectedVariables(lastVariables);
      
      setShowVariableSelection(true);
    }
  };

  // Get current variables (real data only) with transformation filtering and search
  const getCurrentVariables = () => {
    // Only use real data from API
    if (realVariables.length === 0) {
      return []; // No variables if API data not loaded
    }

    const allVariables = realVariables.map(v => ({
      name: v.column_name,
      type: isCategoricalColumn(v) ? 'Categorical' : 'Numerical',
      definition: getVariableDefinition(v.column_name, v.data_type)
    }));

    // Filter variables based on selected transformation
    let filteredVariables;
    if (selectedTransformation === 'Log Transformation') {
      // Only show numerical variables for log transformation
      filteredVariables = allVariables.filter(v => v.type === 'Numerical');
    } else if (selectedTransformation === 'One Hot Encoding') {
      // Only show categorical variables for one hot encoding
      filteredVariables = allVariables.filter(v => v.type === 'Categorical');
    } else {
      // For WOE Transformation, show all variables
      filteredVariables = allVariables;
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filteredVariables = filteredVariables.filter(v => 
        v.name.toLowerCase().includes(query) || 
        v.definition.toLowerCase().includes(query)
      );
    }

    return filteredVariables;
  };

  // Handle Select All for variables
  const handleSelectAllVariables = (checked: boolean) => {
    const currentVars = getCurrentVariables();
    if (checked) {
      setSelectedVariables(currentVars.map(v => v.name));
    } else {
      setSelectedVariables([]);
    }
  };

  // Handle individual variable selection
  const handleVariableToggle = (variableName: string, checked: boolean) => {
    if (checked) {
      setSelectedVariables(prev => [...prev, variableName]);
    } else {
      setSelectedVariables(prev => prev.filter(v => v !== variableName));
    }
  };

  // Handle Submit from Screen2
  const handleScreen2Submit = () => {
    
    // Add transformations to applied transformations
    const newTransformations = { ...appliedTransformations };
    
    // First, remove this transformation from all variables that were previously selected for this transformation
    const lastVariables = lastSelectedVariables[selectedTransformation] || [];
    lastVariables.forEach(variable => {
      if (newTransformations[variable]) {
        const existingTransformations = newTransformations[variable];
        const otherTransformations = existingTransformations
          .split(', ')
          .filter(t => t !== selectedTransformation)
          .join(', ');
        
        if (otherTransformations) {
          newTransformations[variable] = otherTransformations;
        } else {
          delete newTransformations[variable];
        }
      }
    });
    
    // Then, add this transformation to currently selected variables
    selectedVariables.forEach(variable => {
      const existingTransformations = newTransformations[variable] || '';
      
      // Check if this transformation already exists for this variable
      if (existingTransformations.includes(selectedTransformation)) {
        // If same transformation exists, replace it (latest wins)
        const otherTransformations = existingTransformations
          .split(', ')
          .filter(t => t !== selectedTransformation)
          .join(', ');
        
        newTransformations[variable] = otherTransformations 
          ? `${otherTransformations}, ${selectedTransformation}`
          : selectedTransformation;
      } else {
        // If transformation doesn't exist, add it
        newTransformations[variable] = existingTransformations 
          ? `${existingTransformations}, ${selectedTransformation}`
          : selectedTransformation;
      }
    });
    
    setAppliedTransformations(newTransformations);
    
    // Save selected variables for this transformation
    setLastSelectedVariables(prev => ({
      ...prev,
      [selectedTransformation]: selectedVariables
    }));
    
    // Close modal and show Screen3 for review
    setShowVariableSelection(false);
    setShowReviewScreen(true);
  };


  // Handle final report actions
  const handleDownloadReport = () => {
    if (!transformationResponse?.response_data || transformationResponse.response_data.length === 0) {
      alert('No transformation data available to download');
      return;
    }

    try {
      // Prepare data for Excel
      const excelData = transformationResponse.response_data.map((item) => ({
        'New Variable Name': item.new_variable_name,
        'Variable Type': item.var_type,
        'Variable Definition': item.variable_definition,
        'Transformation Methods': item.transformation_methods,
        'Code Logic': item.code_logic
      }));

      // Create worksheet and workbook
      const worksheet = XLSX.utils.json_to_sheet(excelData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Transformed Variables');

      // Set column widths for better readability
      const columnWidths = [
        { wch: 30 }, // New Variable Name
        { wch: 15 }, // Variable Type
        { wch: 40 }, // Variable Definition
        { wch: 25 }, // Transformation Methods
        { wch: 60 }  // Code Logic
      ];
      worksheet['!cols'] = columnWidths;

      // Generate filename with timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
      const filename = `Feature_Transformation_Report_${timestamp}.xlsx`;

      // Download the file
      XLSX.writeFile(workbook, filename);
      console.log('✅ Report downloaded successfully:', filename);
    } catch (error) {
      console.error('❌ Error generating Excel report:', error);
      alert('Failed to generate Excel report');
    }
  };

  // Handle showing code logic
  const handleShowCodeLogic = (codeLogic: string) => {
    setSelectedCodeLogic(codeLogic);
    setShowCodeModal(true);
  };

  // Helper to get split status message
  const getSplitStatusMessage = () => {
    if (useSplit) {
      return `Using split data (${splitRatios.train}% Train, ${splitRatios.test}% Test, ${splitRatios.validation}% Validation): Transformations will be fit on Train and applied to Test/Validation`;
    } else {
      return "Using entire dataset: Transformations will be applied to all data at once";
    }
  };

  // Helper to get split status badge
  const getSplitStatusBadge = () => {
    if (useSplit) {
      const scopeColors = {
        train: 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300',
        test: 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300',
        validation: 'bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300'
      };
      const scopeLabels = {
        train: `Train (${splitRatios.train}%)`,
        test: `Test (${splitRatios.test}%)`,
        validation: `Validation (${splitRatios.validation}%)`
      };
      return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${scopeColors[activeScope]}`}>
          {scopeLabels[activeScope]}
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300">
          Entire Dataset
        </span>
      );
    }
  };

  // Handle scope change from DataSplit component
  const handleScopeChange = (scope: 'train' | 'test' | 'validation') => {
    setActiveScope(scope);
  };

  // Handle Confirm from Screen3
  const handleScreen3Confirm = async () => {
    if (!datasetId) {
      setError('No dataset ID available');
      return;
    }

    setIsTransforming(true);
    setTransformJobId(null);
    setTransformProgress(0);
    setTransformStatusMessage('Starting transformation...');
    setError('');

    try {
      // Build the transformation plan from applied transformations
      const transformationPlan = Object.entries(appliedTransformations)
        .filter(([_, transformations]) => transformations && transformations !== 'No Transformation')
        .map(([variableName, transformations]) => {
          const originalVar = realVariables.find(v => v.column_name === variableName);
          return {
            variable_name: variableName,
            var_type: originalVar && isCategoricalColumn(originalVar) ? 'Char' : 'Num',
            variable_definition: getVariableDefinition(variableName, originalVar?.data_type || ''),
            transformation_methods: transformations.split(', ').map(t => {
              switch (t) {
                case 'WOE Transformation': return 'woe_transformation';
                case 'Log Transformation': return 'log_transformation';
                case 'One Hot Encoding': return 'one_hot_encoding';
                default: return t.toLowerCase().replace(' ', '_');
              }
            })
          };
        });

      if (transformationPlan.length === 0) {
        setError('No transformations selected');
        setIsTransforming(false);
        return;
      }

      // Call the feature transformation API (async job to avoid UI freeze)
      const fastApiService = new FastAPIService();
      const request: FeatureTransformationRequest = {
        dataset_id: datasetId,
        plan_json: JSON.stringify(transformationPlan),
        target_variable: targetVariable, // Use the target variable from props
        woe_bins: 10,
        selected_segments: selectedSegmentsText?.trim() || undefined,
        use_split: useSplit  // Pass split mode from Step 1 configuration
      };

      const startResp = await fastApiService.startFeatureTransformationJob(request);
      if (!startResp.success || !startResp.job_id) {
        setError(startResp.error || 'Failed to start transformation job');
        return;
      }

      const jobId = startResp.job_id;
      setTransformJobId(jobId);
      setTransformStatusMessage('Transformation running...');

      // Poll status
      const pollIntervalMs = 2000;
      let done = false;
      while (!done) {
        await new Promise(resolve => setTimeout(resolve, pollIntervalMs));

        const statusResp = await fastApiService.getFeatureTransformationJobStatus(jobId);
        if (!statusResp.success) {
          setError(statusResp.error || 'Failed to get transformation status');
          return;
        }

        if (typeof statusResp.progress === 'number') {
          setTransformProgress(statusResp.progress);
        }
        if (statusResp.message) {
          setTransformStatusMessage(statusResp.message);
        }

        if (statusResp.status === 'completed') {
          const response = statusResp.results;
          if (!response) {
            setError('Transformation completed but no results returned');
            return;
          }

          setTransformationResponse(response);

          if (response.success) {
            // Convert API response to transformed variables format
            const newTransformedVariables: Record<string, any> = {};

            response.response_data.forEach(item => {
              newTransformedVariables[item.new_variable_name] = {
                originalName: item.new_variable_name.replace(/_transform.*$/, ''),
                transformedName: item.new_variable_name,
                varType: item.var_type,
                definition: item.variable_definition,
                transformationMethods: item.transformation_methods,
                codeLogic: item.code_logic,
                distribution: {
                  original: `Original distribution of ${item.new_variable_name.replace(/_transform.*$/, '')}`,
                  transformed: `Transformed distribution after ${item.transformation_methods}`
                }
              };
            });

            setShowFinalReport(true);
          } else {
            setError(response.error || 'Transformation failed');
          }

          setTransformProgress(100);
          setTransformStatusMessage('Completed');
          done = true;
        } else if (statusResp.status === 'failed') {
          setError(statusResp.error || 'Transformation job failed');
          done = true;
        }
      }
    } catch (err) {
      console.error('Feature transformation failed:', err);
      setError(`Transformation failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsTransforming(false);
    }
  };

  // Optional: selected segments input for segment-wise FE
  const [selectedSegmentsText, setSelectedSegmentsText] = React.useState<string>('');
  const [selectedSegments, setSelectedSegments] = React.useState<number[]>([]);

  // Only show segment options if segmentation has been applied
  const hasSegmentation = segmentationResult?.segments && Array.isArray(segmentationResult.segments) && segmentationResult.segments.length > 0;
  
  const segmentRange: number[] = hasSegmentation && typeof maxSegments === 'number' && maxSegments > 0
    ? Array.from({ length: maxSegments }, (_, i) => i + 1)
    : [];

  // Build segment options with descriptions from segmentation result
  const getSegmentDescription = (segmentId: number, truncate: boolean = false): string => {
    if (!segmentationResult?.segments) return String(segmentId);
    
    const segment = segmentationResult.segments.find(
      (s: any, idx: number) => (s.leaf_id === segmentId || idx + 1 === segmentId)
    );
    
    if (!segment) return String(segmentId);
    
    const rules = segment.rules_readable || 
                  (Array.isArray(segment.rules) && segment.rules.length > 0 
                    ? segment.rules.join(' AND ') 
                    : '');
    
    const fullDescription = rules ? `Segment ${segmentId}: ${rules}` : `Segment ${segmentId}`;
    
    // Truncate if requested and text is too long
    if (truncate && fullDescription.length > 80) {
      return fullDescription.substring(0, 77) + '...';
    }
    
    return fullDescription;
  };

  return (
    <div className="space-y-6">
      <UserKnowledgeUploadPanel datasetId={activeDatasetId || datasetId || null} scope="feature_engineering" />

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Feature Engineering</h3>
        
        {/* Feature Engineering Steps Section */}
        <div className="mb-6">
          {/* Split Status Indicator with Train/Test/Validation */}
          {useSplit ? (
            <div className="mb-4">
              <DataSplit
                datasetAnalysis={null}
                mode="other"
                showLockedInfo={true}
                selectedScope={activeScope}
                onScopeChange={handleScopeChange}
              />
            </div>
          ) : (
            <div className="mb-4 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/40 dark:to-indigo-900/40 border border-purple-200 dark:border-purple-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Data Processing Mode</span>
                    {getSplitStatusBadge()}
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400">{getSplitStatusMessage()}</p>
                </div>
              </div>
            </div>
          )}

          {/* Apply to segments */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Apply to segments <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-3">
              <select
                value={selectedSegments.length === 1 ? String(selectedSegments[0]) : ''}
                onChange={(e) => {
                  const val = e.target.value;
                  if (!val) {
                    // All segments (global)
                    setSelectedSegments([]);
                    setSelectedSegmentsText('');
                  } else {
                    const n = parseInt(val, 10);
                    if (!isNaN(n)) {
                      setSelectedSegments([n]);
                      setSelectedSegmentsText(String(n));
                    }
                  }
                }}
                required
                className="w-full max-w-2xl border rounded px-3 py-2 text-sm text-gray-800 dark:text-gray-100 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">No segments</option>
                {segmentRange.map(seg => (
                  <option 
                    key={seg} 
                    value={String(seg)}
                    title={getSegmentDescription(seg, false)}
                  >
                    {getSegmentDescription(seg, true)}
                  </option>
                ))}
              </select>
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {hasSegmentation 
                ? "Select a specific segment to create per-segment columns (e.g., var_seg1_transform_woe) filled only for that segment, or choose 'No segments' for global columns." 
                : "No segmentation applied. Choose 'No segments' to create global columns for all rows."}
            </p>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-700 mb-4">
            <div className="space-y-3">
              <label className="flex items-center space-x-3">
                <input 
                  type="radio" 
                  name="transformation"
                  className="text-blue-600"
                  checked={selectedFeatureSteps.includes('woe_transformation')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedFeatureSteps(['woe_transformation']);
                    }
                  }}
                />
                <span className="text-sm text-gray-800 dark:text-gray-200">WOE Transformation</span>
              </label>
              
              <label className="flex items-center space-x-3">
                <input 
                  type="radio" 
                  name="transformation"
                  className="text-blue-600"
                  checked={selectedFeatureSteps.includes('log_transformation')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedFeatureSteps(['log_transformation']);
                    }
                  }}
                />
                <span className="text-sm text-gray-800 dark:text-gray-200">Log transformation (Numerical variables only)</span>
              </label>
              
              <label className="flex items-center space-x-3">
                <input 
                  type="radio" 
                  name="transformation"
                  className="text-blue-600"
                  checked={selectedFeatureSteps.includes('one_hot_encoding')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedFeatureSteps(['one_hot_encoding']);
                    }
                  }}
                />
                <span className="text-sm text-gray-800 dark:text-gray-200">One Hot Encoding (for classification variables)</span>
              </label>
            </div>
          </div>
          
          <button
            onClick={handleScreen1Submit}
            disabled={selectedFeatureSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Submit
          </button>
        </div>


        {/* Screen2: Variable Selection Modal - This will pop up after Screen1 Submit */}
        {showVariableSelection && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden animate-in fade-in-0 zoom-in-95 duration-300 border border-gray-200 dark:border-gray-700">
              {/* Modal Header */}
              <div className="flex justify-between items-center p-6 border-b border-gray-200 dark:border-gray-700">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Variable Selection</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                    Select variables for <span className="font-semibold text-green-600 dark:text-green-400">{selectedTransformation}</span> transformation
                  </p>
                </div>
                <button 
                  onClick={() => setShowVariableSelection(false)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors p-1"
                >
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              {/* Modal Content */}
              <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
                {/* Search Box */}
          <div className="mb-6">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search variables by name or type..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full px-4 py-3 pl-12 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    />
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="absolute inset-y-0 right-0 pr-4 flex items-center hover:bg-gray-100 dark:hover:bg-gray-700 rounded-r-lg transition-colors"
                      >
                        <svg className="h-5 w-5 text-gray-400 hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                  {searchQuery && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                      Showing {getCurrentVariables().length} variables matching "{searchQuery}"
                    </p>
                  )}
                </div>
                
                {/* Variables Table */}
                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="overflow-y-auto max-h-96">
                    <table className="w-full">
                      <thead className="bg-gray-100 dark:bg-gray-700 sticky top-0">
                        <tr className="border-b border-gray-200 dark:border-gray-600">
                          <th className="text-left py-3 px-4">
                            <label className="flex items-center space-x-2">
                              <input 
                                type="checkbox" 
                                className="rounded text-green-600"
                                checked={selectedVariables.length === getCurrentVariables().length && getCurrentVariables().length > 0}
                                onChange={(e) => handleSelectAllVariables(e.target.checked)}
                              />
                              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Select All</span>
                            </label>
                          </th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-700 dark:text-gray-200">Variable Name</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-700 dark:text-gray-200">Var Type</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-700 dark:text-gray-200">Variable definition/Classification</th>
                        </tr>
                      </thead>
                      <tbody>
                        {loading ? (
                          <tr>
                            <td colSpan={4} className="py-12 px-4 text-center text-gray-500 dark:text-gray-300">
                              <div className="flex items-center justify-center space-x-3">
                                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-green-600"></div>
                                <span>Loading variables...</span>
                              </div>
                            </td>
                          </tr>
                        ) : error ? (
                          <tr>
                            <td colSpan={4} className="py-12 px-4 text-center">
                              <div className="text-red-500 mb-2">{error}</div>
                              <div className="text-sm text-gray-600 dark:text-gray-300">Please check your dataset and try again</div>
                            </td>
                          </tr>
                        ) : getCurrentVariables().length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-12 px-4 text-center text-gray-500 dark:text-gray-300">
                              {searchQuery ? 
                                `No variables found matching "${searchQuery}"` : 
                                'No variables available for the selected transformation'
                              }
                            </td>
                          </tr>
                        ) : (
                          getCurrentVariables().map((variable, index) => (
                            <tr key={variable.name} className={`border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${index % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-gray-50 dark:bg-gray-800'}`}>
                              <td className="py-3 px-4">
                                <input 
                                  type="checkbox" 
                                  className="rounded text-green-600"
                                  checked={selectedVariables.includes(variable.name)}
                                  onChange={(e) => handleVariableToggle(variable.name, e.target.checked)}
                                />
                              </td>
                              <td className="py-3 px-4 text-sm text-gray-800 dark:text-gray-100 font-medium">{variable.name}</td>
                              <td className="py-3 px-4 text-sm text-gray-800 dark:text-gray-100">
                                <span className={`px-2 py-1 rounded text-xs ${
                                  variable.type === 'Numerical'
                                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
                                    : 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200'
                                }`}>
                                  {variable.type}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-300">{variable.definition}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
              
              {/* Modal Footer */}
              <div className="flex justify-between items-center p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  {selectedVariables.length > 0 && (
                    <span>{selectedVariables.length} variable(s) selected</span>
                  )}
                </div>
                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowVariableSelection(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleScreen2Submit}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Apply Transformation
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Screen3: Review/Confirmation Section - This will show after Screen2 Submit */}
        {showReviewScreen && (
          <div className="mb-6 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-6 border border-yellow-200 dark:border-yellow-700">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Review the transformation logic</h4>
            
            <div className="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700 mb-4">
              <div className="overflow-y-auto max-h-64 overflow-x-auto">
                <table className="w-full">
                  <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 bg-white dark:bg-gray-900">
                        <label className="flex items-center space-x-2">
                          <input 
                            type="checkbox" 
                            className="rounded text-yellow-600"
                            checked={true}
                            readOnly
                          />
                          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Select All</span>
                        </label>
                      </th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900">Variable Name</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900">Var Type</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900">Variable definition</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900">Transformation method</th>
                    </tr>
                  </thead>
                  <tbody>
                    {realVariables.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 px-4 text-center text-gray-500 dark:text-gray-300">
                          {loading ? 'Loading variables...' : 
                           error ? `Error: ${error}` : 
                           'No variables available'}
                        </td>
                      </tr>
                    ) : (
                      realVariables.map((variable, index) => {
                        const variableName = variable.column_name;
                        const variableType = isCategoricalColumn(variable) ? 'Categorical' : 'Numerical';
                        const variableDefinition = getVariableDefinition(variableName, variable.data_type);
                        const hasTransformation = appliedTransformations[variableName];
                        const transformationMethod = hasTransformation || 'No Transformation';
                        
                        return (
                      <tr key={variableName} className={`border-b border-gray-100 dark:border-gray-700 ${index % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-gray-50 dark:bg-gray-800'}`}>
                        <td className="py-2 px-3">
                          <input 
                            type="checkbox" 
                                className="rounded text-yellow-600"
                                checked={!!hasTransformation}
                                readOnly
                          />
                        </td>
                        <td className="py-2 px-3 text-sm text-gray-800 dark:text-gray-100">{variableName}</td>
                        <td className="py-2 px-3 text-sm text-gray-800 dark:text-gray-100">{variableType}</td>
                        <td className="py-2 px-3 text-sm text-gray-600 dark:text-gray-300">{variableDefinition}</td>
                            <td className="py-2 px-3 text-sm text-gray-600">
                              <span className={`px-2 py-1 rounded text-xs ${
                                hasTransformation 
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200' 
                                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                              }`}>
                                {transformationMethod}
                              </span>
                            </td>
                      </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            
            {error && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg">
                <div className="text-red-600 dark:text-red-400 text-sm">{error}</div>
              </div>
            )}
            
            <div className="flex space-x-3">
              <button
                onClick={handleScreen3Confirm}
                disabled={isTransforming}
                className="px-4 py-2 bg-yellow-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-yellow-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
              >
                {isTransforming ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Applying Transformations...</span>
                  </>
                ) : (
                  <span>Confirm</span>
                )}
              </button>

              {isTransforming && (
                <div className="mt-3 w-full">
                  <div className="text-xs text-gray-700">
                    {transformStatusMessage || 'Working...'}
                    {transformJobId ? ` (Job: ${transformJobId})` : ''}
                  </div>
                  <div className="mt-2 w-full bg-gray-200 rounded h-2 overflow-hidden">
                    <div
                      className="bg-yellow-600 h-2 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, transformProgress))}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Screen4: Final Report Section */}
        {showFinalReport && (
          <div className="mb-6 bg-green-50 dark:bg-green-900/20 rounded-lg p-6 border border-green-200 dark:border-green-700">
            <div className="flex justify-between items-center mb-4">
              <h4 className="font-medium text-gray-900 dark:text-gray-100">Transformed Variables</h4>
              <div className="flex space-x-2">
                <button
                  onClick={handleDownloadReport}
                  className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                >
                  Download Report
                </button>
              </div>
            </div>
            
            {/* Transformed Variables Table */}
            <div className="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700 mb-4">
              <div className="overflow-y-auto max-h-96">
                <table className="w-full">
                  <thead className="bg-white dark:bg-gray-900 sticky top-0 z-10">
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200">New Transformed Variable</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200">Var Type</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200">Variable definition</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200">Transformation method</th>
                      <th className="text-left py-2 px-3 text-sm font-medium text-gray-700 dark:text-gray-200">Code logic</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transformationResponse?.response_data?.map((item, index) => (
                      <tr key={item.new_variable_name} className={`border-b border-gray-100 dark:border-gray-700 ${index % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-gray-50 dark:bg-gray-800'}`}>
                        <td className="py-2 px-3 text-sm text-gray-800 dark:text-gray-100 font-medium">{formatVariableName(item.new_variable_name)}</td>
                        <td className="py-2 px-3 text-sm text-gray-800 dark:text-gray-100">
                          {item.var_type}
                        </td>
                        <td className="py-2 px-3 text-sm text-gray-600 dark:text-gray-300">{item.variable_definition}</td>
                        <td className="py-2 px-3 text-sm text-gray-600">
                          <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200">
                            {item.transformation_methods}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-sm text-gray-600">
                          <button
                            onClick={() => handleShowCodeLogic(item.code_logic)}
                            className="text-blue-600 hover:text-blue-800 underline text-xs"
                          >
                            View Code logic
                          </button>
                        </td>
                      </tr>
                    )) || (
                      <tr>
                        <td colSpan={5} className="py-12 px-4 text-center text-gray-500 dark:text-gray-300">
                          No transformations applied yet
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Code Logic Modal */}
      {showCodeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden animate-in fade-in-0 zoom-in-95 duration-300 border border-gray-200 dark:border-gray-700">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-6 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Code Logic</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                  Generated Python code for the transformation
                </p>
              </div>
              <button 
                onClick={() => setShowCodeModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors p-1"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
              <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                   {formatCodeLogic(selectedCodeLogic)}
                </pre>
              </div>
            </div>
            
            {/* Modal Footer */}
            <div className="flex justify-end items-center p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
              <button
                onClick={() => setShowCodeModal(false)}
                className="px-4 py-2 bg-gray-600 dark:bg-gray-700 text-white rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chat Component */}
      {renderStepChat(4)}
    </div>
  );
};

export default Step4FeatureEngineering;
