import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Database, Plus, Brain, GripVertical, X, Loader2, CheckCircle2, Settings2, Upload, Download } from 'lucide-react';
import DataSplit from '../DataSplit';
import UserKnowledgeUploadPanel from '../UserKnowledgeUploadPanel';
import DuplicateRemovalPanel from '../DuplicateRemovalPanel';
import { buildMidasAuthHeaders } from '../../services/authHeaders';

/**
 * Interface for dataset column information
 */
interface DatasetColumnInfo {
  name: string;
  type: 'Numerical' | 'Categorical';
  pandas_type: string;
  unique_count: number;
  missing_count: number;
  logical_type?: 'Numerical' | 'Categorical' | 'Date' | string;
  is_date?: boolean;
}

/**
 * Props interface for Step2DataQC component.
 *
 * Duplicate-removal state is lifted to ModelBuilder so it persists when the
 * user navigates between pages.
 */
interface Step2DataQCProps {
  selectedDataSources: any[];
  onDataSourceSelect: (dataSource: any) => void;
  onRemoveDataSource: (index: number) => void;
  showDataSourceSelectionModal: boolean;
  setShowDataSourceSelectionModal: (show: boolean) => void;
  activeDatasetId: string | null;
  datasetAnalysis?: {
    totalRows: number;
    totalColumns?: number;
    columns?: DatasetColumnInfo[];
    totalColumns?: number;
    columns?: DatasetColumnInfo[];
  } | null;
  selectedQCTasks: string[];
  setSelectedQCTasks: (tasks: string[] | ((prev: string[]) => string[])) => void;
  onAutoQC: () => Promise<void>;
  onStandardQC: () => Promise<void>;
  onQCTaskToggle: (task: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;

  // ── Duplicate removal state (lifted to parent for persistence) ──────────────
  /** null = not answered, true = Yes, false = No */
  wantsToRemoveDuplicates: boolean | null;
  onWantsToRemoveDuplicatesChange: (v: boolean | null) => void;
  isDuplicateRemovalComplete: boolean;
  onDuplicateRemovalComplete: (result: { removedCount: number; newRowCount: number }) => void;
  isSkipped: boolean;
  onSkip: () => void;
  removalResult: { removedCount: number; newRowCount: number } | null;
  dupSelectedVariables: string[];
  onDupSelectedVariablesChange: (v: string[]) => void;
  dupIdentificationResult: {
    duplicateCount: number;
    totalRows: number;
    duplicatePercentage: number;
    selectedColumns: string[];
    analysisScope: 'train' | 'entire' | string;
  } | null;
  onDupIdentificationResultChange: (
    v: {
      duplicateCount: number;
      totalRows: number;
      duplicatePercentage: number;
      selectedColumns: string[];
      analysisScope: 'train' | 'entire' | string;
    } | null
  ) => void;

  // ── Sidebar / EDA callbacks ─────────────────────────────────────────────────
  onOpenSidebar?: () => void;

  // ── QC Templates callback ─────────────────────────────────────────────────
  onQcTemplatesChange?: (templates: Record<string, any> | null) => void;
}

/**
 * Step2DataQC — Data Treatment Page Component
 *
 * Duplicate-removal state is owned by ModelBuilder and passed in as props so
 * the user's choices are preserved when navigating away and back.
 */
const Step2DataQC: React.FC<Step2DataQCProps> = ({
  selectedDataSources,
  onDataSourceSelect,
  onRemoveDataSource,
  showDataSourceSelectionModal,
  setShowDataSourceSelectionModal,
  activeDatasetId,
  datasetAnalysis,
  selectedQCTasks,
  setSelectedQCTasks,
  onAutoQC,
  onStandardQC,
  onQCTaskToggle,
  renderStepChat,
  wantsToRemoveDuplicates,
  onWantsToRemoveDuplicatesChange,
  isDuplicateRemovalComplete,
  onDuplicateRemovalComplete,
  isSkipped,
  onSkip,
  removalResult,
  dupSelectedVariables,
  onDupSelectedVariablesChange,
  dupIdentificationResult,
  onDupIdentificationResultChange,
  onOpenSidebar,
  onQcTemplatesChange,
}) => {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [isAutoQCRunning, setIsAutoQCRunning] = useState(false);
  const [autoQCCurrentStep, setAutoQCCurrentStep] = useState<number>(0);
  const [autoQCCompletedSteps, setAutoQCCompletedSteps] = useState<string[]>([]);

  const [isManualQCRunning, setIsManualQCRunning] = useState(false);
  const [manualQCCurrentStep, setManualQCCurrentStep] = useState<number>(0);
  const [manualQCCompletedSteps, setManualQCCompletedSteps] = useState<string[]>([]);
  const [showManualQCProgress, setShowManualQCProgress] = useState(false);
  const [showManualQCCard, setShowManualQCCard] = useState(false);

  // Template upload state
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([]);
  const [uploadedTemplates, setUploadedTemplates] = useState<Record<string, File | null>>({});
  const fileInputRefs = {
    invalid_values: useRef<HTMLInputElement>(null),
    special_values: useRef<HTMLInputElement>(null),
    outliers: useRef<HTMLInputElement>(null),
    missing_values: useRef<HTMLInputElement>(null),
  };

  const handleTemplateToggle = (key: string, checked: boolean) => {
    if (checked) {
      setSelectedTemplates(prev => [...prev, key]);
    } else {
      setSelectedTemplates(prev => prev.filter(t => t !== key));
      setUploadedTemplates(prev => ({ ...prev, [key]: null }));
    }
  };

  const handleFileUpload = (key: string, file: File | null) => {
    setUploadedTemplates(prev => ({ ...prev, [key]: file }));
  };

  // Parse CSV template file into structured data for backend
  const parseTemplateCSV = async (file: File, templateType: string): Promise<Record<string, any>> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string;
          const lines = text.trim().split('\n');
          const headers = lines[0].split(',').map(h => h.trim());
          
          const result: Record<string, any> = {};
          
          for (let i = 1; i < lines.length; i++) {
            // Parse CSV line handling quoted values
            const values: string[] = [];
            let current = '';
            let inQuotes = false;
            
            for (const char of lines[i]) {
              if (char === '"') {
                inQuotes = !inQuotes;
              } else if (char === ',' && !inQuotes) {
                values.push(current.trim());
                current = '';
              } else {
                current += char;
              }
            }
            values.push(current.trim());
            
            const varName = values[0];
            if (!varName) continue;
            
            if (templateType === 'invalid_values') {
              // Format: Var Name, Type, Valid Range / Valid Labels
              const type = values[1]?.toLowerCase() || '';
              const validRangeOrLabels = values[2] || '';
              
              try {
                if (type === 'numerical') {
                  // Parse range like "[500, 50000]"
                  const rangeMatch = validRangeOrLabels.match(/\[?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]?/);
                  if (rangeMatch) {
                    result[varName] = {
                      type: 'numerical',
                      valid_range: [parseFloat(rangeMatch[1]), parseFloat(rangeMatch[2])]
                    };
                  }
                } else {
                  // Parse labels like "['A', 'B', 'C']"
                  const labelsMatch = validRangeOrLabels.match(/\[([^\]]+)\]/);
                  if (labelsMatch) {
                    const labels = labelsMatch[1].split(',').map(l => 
                      l.trim().replace(/^['"]|['"]$/g, '')
                    );
                    result[varName] = {
                      type: 'categorical',
                      valid_labels: labels
                    };
                  }
                }
              } catch (parseErr) {
                console.warn(`Failed to parse row for ${varName}:`, parseErr);
              }
            } else if (templateType === 'special_values') {
              // Format: Var Name, Type, Special Values
              const type = values[1]?.toLowerCase() || '';
              const specialValuesStr = values[2] || '';
              
              try {
                // Parse special values like "[-999, -1, 0]"
                const valuesMatch = specialValuesStr.match(/\[([^\]]+)\]/);
                if (valuesMatch) {
                  const specialVals = valuesMatch[1].split(',').map(v => {
                    const trimmed = v.trim().replace(/^['"]|['"]$/g, '');
                    const num = parseFloat(trimmed);
                    return isNaN(num) ? trimmed : num;
                  });
                  result[varName] = {
                    type: type,
                    special_values: specialVals
                  };
                }
              } catch (parseErr) {
                console.warn(`Failed to parse row for ${varName}:`, parseErr);
              }
            } else if (templateType === 'outliers') {
              // Format: Var Name, Type, Choose Detection Method
              const type = values[1]?.toLowerCase() || '';
              const method = values[2] || '';
              
              result[varName] = {
                type: type,
                detection_method: method
              };
            } else if (templateType === 'missing_values') {
              // Format: Var Name, Type, Choose Imputation Method
              const type = values[1]?.toLowerCase() || '';
              const method = values[2] || '';
              
              result[varName] = {
                type: type,
                imputation_method: method
              };
            }
          }
          
          resolve(result);
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  };

  // Effect to parse uploaded templates and notify parent
  React.useEffect(() => {
    const parseAllTemplates = async () => {
      const parsedTemplates: Record<string, any> = {};
      let hasAnyTemplate = false;
      
      for (const [key, file] of Object.entries(uploadedTemplates)) {
        if (file) {
          try {
            console.log(`📄 Parsing ${key} template: ${file.name}`);
            const parsed = await parseTemplateCSV(file, key);
            console.log(`✅ Parsed ${key} template:`, parsed);
            if (Object.keys(parsed).length > 0) {
              parsedTemplates[key] = parsed;
              hasAnyTemplate = true;
            }
          } catch (err) {
            console.error(`❌ Failed to parse ${key} template:`, err);
          }
        }
      }
      
      console.log('📦 All parsed templates:', hasAnyTemplate ? parsedTemplates : null);
      if (onQcTemplatesChange) {
        onQcTemplatesChange(hasAnyTemplate ? parsedTemplates : null);
      }
    };
    
    parseAllTemplates();
  }, [uploadedTemplates, onQcTemplatesChange]);

  const handleDownloadTemplate = async (templateKey: string) => {
    // Get columns from datasetAnalysis to send to backend
    const datasetColumns = datasetAnalysis?.columns || [];
    
    try {
      // Call backend API to generate template with proper Excel data validation
      const authHeaders = buildMidasAuthHeaders();
      const response = await fetch(`/api/upload/generate-qc-template/${templateKey}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        body: JSON.stringify({
          columns: datasetColumns.map(col => ({
            name: col.name,
            type: col.type,
            is_date: col.is_date,
            logical_type: col.logical_type,
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to generate template: ${response.statusText}`);
      }

      // Get the file blob from response
      const blob = await response.blob();
      
      // Determine filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${templateKey}_template.${templateKey === 'outliers' || templateKey === 'missing_values' ? 'xlsx' : 'csv'}`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create download link
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Error downloading template:', error);
      
      // Fallback to client-side generation if backend fails
      const templateHeaders: Record<string, string[]> = {
        invalid_values: ['Var Name', 'Type', 'Valid Range / Valid Labels'],
        special_values: ['Var Name', 'Type', 'Special Values'],
        outliers: ['Var Name', 'Type', 'Choose Detection Method'],
        missing_values: ['Var Name', 'Type', 'Choose Imputation Method'],
      };

      const headers = templateHeaders[templateKey];
      if (!headers) return;

      // Filter columns
      const filteredColumns = datasetColumns.filter(col => {
        if (col.is_date === true || col.logical_type === 'Date') return false;
        return col.type === 'Numerical' || col.type === 'Categorical';
      });

      // Generate CSV as fallback
      let csvContent = headers.join(',') + '\n';
      filteredColumns.forEach(col => {
        const varName = col.name.includes(',') ? `"${col.name}"` : col.name;
        csvContent += `${varName},${col.type || 'Unknown'},\n`;
      });

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${templateKey}_template.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  const autoQCSteps = [
    { id: 'invalid_values', label: '1. Treating Invalid Values' },
    { id: 'special_values', label: '2. Treating Special Values' },
    { id: 'outliers', label: '3. Treating Outliers' },
    { id: 'missing_values', label: '4. Treating Missing Values' },
  ];

  const handleManualQCWithProgress = async () => {
    if (selectedQCTasks.length === 0) return;
    
    setIsManualQCRunning(true);
    setShowManualQCProgress(true);
    setManualQCCurrentStep(0);
    setManualQCCompletedSteps([]);

    // Simulate progress through selected tasks
    for (let i = 0; i < selectedQCTasks.length; i++) {
      setManualQCCurrentStep(i);
      await new Promise(resolve => setTimeout(resolve, 800));
      setManualQCCompletedSteps(prev => [...prev, selectedQCTasks[i]]);
    }

    // Call the actual onStandardQC handler
    try {
      await onStandardQC();
    } finally {
      setIsManualQCRunning(false);
    }
  };

  const handleAutoQCWithProgress = async () => {
    setIsAutoQCRunning(true);
    setAutoQCCurrentStep(0);
    setAutoQCCompletedSteps([]);

    // Simulate progress through steps
    for (let i = 0; i < autoQCSteps.length; i++) {
      setAutoQCCurrentStep(i);
      await new Promise(resolve => setTimeout(resolve, 800)); // Simulate step processing
      setAutoQCCompletedSteps(prev => [...prev, autoQCSteps[i].id]);
    }

    // Call the actual onAutoQC handler
    try {
      await onAutoQC();
    } finally {
      setIsAutoQCRunning(false);
      setAutoQCCurrentStep(0);
    }
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    const newTasks = [...selectedQCTasks];
    const [draggedItem] = newTasks.splice(draggedIndex, 1);
    newTasks.splice(dropIndex, 0, draggedItem);
    setSelectedQCTasks(newTasks);
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const removeTask = (index: number) => {
    const taskToRemove = selectedQCTasks[index];
    onQCTaskToggle(taskToRemove, false);
  };

  const getTaskDisplayName = (task: string): string => {
    const displayNames: Record<string, string> = {
      'missing_values': 'Missing Values',
      'outliers': 'Outliers',
      'invalid_values': 'Invalid Values',
      'special_values': 'Special Values'
    };
    return displayNames[task] || task;
  };

  // Available columns (excluding data split identifier)
  const availableColumns = useMemo(() => {
    if (!datasetAnalysis?.columns) return [];
    return datasetAnalysis.columns.map(col => col.name);
  }, [datasetAnalysis]);

  // Determine whether to show the rest of the page
  const showOtherComponents = isDuplicateRemovalComplete || isSkipped || wantsToRemoveDuplicates === false;

  return (
    <div className="space-y-6">
      {/* Data Split Component */}
      <DataSplit activeDatasetId={activeDatasetId} datasetAnalysis={datasetAnalysis} stepKey={2} showSamplingUI={false} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Data Treatment</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Validate data quality and readiness. Upload files or choose from available datasets.
          </p>
        </div>
        <button
          onClick={() => setShowDataSourceSelectionModal(true)}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="h-5 w-5" />
          <span>Add Data Source</span>
        </button>
      </div>

      <UserKnowledgeUploadPanel datasetId={activeDatasetId} scope="data_treatment" />

      {/* No dataset selected placeholder */}
      {selectedDataSources.length === 0 && !activeDatasetId && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <div className="max-w-md mx-auto">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Database className="h-8 w-8 text-blue-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Select Data Sources</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Upload files, connect to databases, or integrate with cloud services to get started.
            </p>
            <button
              onClick={() => setShowDataSourceSelectionModal(true)}
              className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-5 w-5 mr-2" />
              Click to open data source selection
            </button>
          </div>
        </div>
      )}

      {/* Duplicate Removal Panel — always shown when dataset is loaded */}
      {activeDatasetId && (
        <DuplicateRemovalPanel
          datasetId={activeDatasetId}
          availableColumns={availableColumns}
          dataSplitColumn="data_split_identifier"
          onDuplicatesRemoved={onDuplicateRemovalComplete}
          onSelectionChange={onWantsToRemoveDuplicatesChange}
          wantsToRemoveDuplicates={wantsToRemoveDuplicates}
          isDuplicateRemovalComplete={isDuplicateRemovalComplete}
          isSkipped={isSkipped}
          onSkip={onSkip}
          onOpenSidebar={onOpenSidebar}
          removalResult={removalResult}
          selectedVariables={dupSelectedVariables}
          onSelectedVariablesChange={onDupSelectedVariablesChange}
          identificationResult={dupIdentificationResult}
          onIdentificationResultChange={onDupIdentificationResultChange}
        />
      )}

      {/* Mandatory selection notice */}
      {activeDatasetId && wantsToRemoveDuplicates === null && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            <strong>Note:</strong> Please select whether you want to remove duplicates before proceeding with other data treatment tasks.
          </p>
        </div>
      )}

      {/* Rest of data treatment — shown after duplicate decision */}
      {showOtherComponents && (
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Data Treatment</h3>

          {/* Upload CSV Template Section */}
          <div className="mb-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg border border-green-200 dark:border-green-700">
            <h5 className="font-medium text-green-900 dark:text-green-200 mb-3">Upload CSV Template <span className="font-normal text-gray-500 dark:text-gray-400">(optional)</span></h5>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              Select the treatment types you want to upload templates for
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              {[
                { key: 'invalid_values', label: 'Invalid Values' },
                { key: 'special_values', label: 'Special Values' },
                { key: 'outliers', label: 'Outliers' },
                { key: 'missing_values', label: 'Missing Values' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="rounded text-green-600"
                    checked={selectedTemplates.includes(key)}
                    onChange={(e) => handleTemplateToggle(key, e.target.checked)}
                  />
                  <span className="text-sm text-green-800 dark:text-green-300">{label}</span>
                </label>
              ))}
            </div>

            {/* Upload sections for selected templates */}
            {selectedTemplates.length > 0 && (
              <div className="space-y-3 mt-4 pt-4 border-t border-green-200 dark:border-green-700">
                {selectedTemplates.map((templateKey) => {
                  const templateLabels: Record<string, string> = {
                    invalid_values: 'Invalid Values',
                    special_values: 'Special Values',
                    outliers: 'Outliers',
                    missing_values: 'Missing Values',
                  };
                  const uploadedFile = uploadedTemplates[templateKey];
                  
                  const columnHints: Record<string, React.ReactNode> = {
                    invalid_values: (
                      <>
                        <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Var Name</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Type</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Valid Range / Valid Labels</code>
                      </>
                    ),
                    special_values: (
                      <>
                        <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Var Name</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Type</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Special Values</code>
                      </>
                    ),
                    outliers: (
                      <>
                        <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Var Name</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Type</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Choose Detection Method</code>
                      </>
                    ),
                    missing_values: (
                      <>
                        <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Var Name</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Type</code> | <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">Choose Imputation Method</code>
                      </>
                    ),
                  };
                  
                  return (
                    <div key={templateKey} className="bg-white/70 dark:bg-gray-800/50 rounded-lg p-3 border border-green-100 dark:border-green-800">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-green-900 dark:text-green-200">
                          {templateLabels[templateKey]}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                        Upload a CSV file with columns: {columnHints[templateKey]}
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={() => handleDownloadTemplate(templateKey)}
                          className="px-3 py-1.5 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700 transition-colors flex items-center space-x-2"
                        >
                          <Download className="h-4 w-4" />
                          <span>Download CSV Template</span>
                        </button>
                        <input
                          type="file"
                          accept=".csv"
                          ref={fileInputRefs[templateKey as keyof typeof fileInputRefs]}
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            handleFileUpload(templateKey, file);
                          }}
                        />
                        <button
                          onClick={() => fileInputRefs[templateKey as keyof typeof fileInputRefs].current?.click()}
                          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
                        >
                          <Upload className="h-4 w-4" />
                          <span>Upload CSV Template</span>
                        </button>
                        {uploadedFile && (
                          <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                            <CheckCircle2 className="h-4 w-4" />
                            <span>{uploadedFile.name}</span>
                            <button
                              onClick={() => handleFileUpload(templateKey, null)}
                              className="p-0.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-gray-400 hover:text-red-500"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Standard QC */}
          <div className="mb-2">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Standard QC Tasks</h4>

            {/* QC Buttons Section */}
            <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg border border-blue-200 dark:border-blue-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                Analyze missingness, outliers, invalid values, special values
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleAutoQCWithProgress}
                  disabled={isAutoQCRunning || showManualQCCard}
                  className={`px-4 py-2 rounded-lg transition-colors flex items-center space-x-2 ${
                    showManualQCCard
                      ? 'bg-blue-300 text-white cursor-not-allowed opacity-50'
                      : 'bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'
                  }`}
                >
                  {isAutoQCRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Running Auto QC...</span>
                    </>
                  ) : (
                    <>
                      <Brain className="h-4 w-4" />
                      <span>Run Auto Data QC</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowManualQCCard(!showManualQCCard)}
                  disabled={isAutoQCRunning}
                  className={`px-4 py-2 rounded-lg transition-colors flex items-center space-x-2 ${
                    isAutoQCRunning
                      ? 'bg-purple-300 text-white cursor-not-allowed opacity-50'
                      : showManualQCCard
                        ? 'bg-purple-700 text-white ring-2 ring-purple-400'
                        : 'bg-purple-600 text-white hover:bg-purple-700'
                  }`}
                >
                  <Settings2 className="h-4 w-4" />
                  <span>Run Manual Data QC</span>
                </button>
              </div>

              {/* Auto QC Progress Steps */}
              {isAutoQCRunning && (
                <div className="mt-4 space-y-2">
                  {autoQCSteps.map((step, index) => {
                    const isCompleted = autoQCCompletedSteps.includes(step.id);
                    const isCurrent = autoQCCurrentStep === index && !isCompleted;
                    return (
                      <div
                        key={step.id}
                        className={`flex items-center gap-2 text-sm transition-all duration-300 ${
                          isCompleted
                            ? 'text-green-600 dark:text-green-400'
                            : isCurrent
                              ? 'text-blue-600 dark:text-blue-400 font-medium'
                              : 'text-gray-400 dark:text-gray-500'
                        }`}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : isCurrent ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <div className="h-4 w-4 rounded-full border-2 border-gray-300 dark:border-gray-600" />
                        )}
                        <span>{step.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Manual QC Section - shown only when Manual QC button is clicked */}
            {showManualQCCard && (
              <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg border border-purple-200 dark:border-purple-700">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Select specific data quality checks to run
                </p>

                {/* Data Treatment Tasks Checkboxes */}
                <div className="bg-white/50 dark:bg-gray-800/50 rounded-lg p-4 border border-purple-100 dark:border-purple-800 mb-4">
                  <h5 className="font-medium text-purple-900 dark:text-purple-200 mb-3">Data Treatment Tasks</h5>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { key: 'invalid_values', label: 'Invalid Values' },
                      { key: 'special_values', label: 'Special Values' },
                      { key: 'outliers', label: 'Outliers' },
                      { key: 'missing_values', label: 'Missing Values' },
                    ].map(({ key, label }) => (
                      <label key={key} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          className="rounded text-purple-600"
                          checked={selectedQCTasks.includes(key)}
                          onChange={(e) => onQCTaskToggle(key, e.target.checked)}
                        />
                        <span className="text-sm text-purple-800 dark:text-purple-300">{label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Choose Treatment Sequence - Draggable Tiles */}
                {selectedQCTasks.length > 0 && (
                  <div className="mb-4">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Choose Treatment Sequence</span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-2">
                      Drag to reorder steps or skip any treatment type. The workflow will execute in the chosen order.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {selectedQCTasks.map((task, index) => (
                        <div
                          key={`qc-tile-${index}`}
                          draggable
                          onDragStart={(e) => handleDragStart(e, index)}
                          onDragOver={(e) => handleDragOver(e, index)}
                          onDragLeave={handleDragLeave}
                          onDrop={(e) => handleDrop(e, index)}
                          onDragEnd={handleDragEnd}
                          className={`
                            flex items-center gap-2 px-3 py-2 rounded-lg border transition-all duration-200 cursor-grab active:cursor-grabbing select-none
                            ${draggedIndex === index 
                              ? 'opacity-50 scale-95 bg-purple-100 dark:bg-purple-900/40 border-purple-300 dark:border-purple-600' 
                              : dragOverIndex === index
                                ? 'bg-purple-50 dark:bg-purple-900/30 border-purple-400 dark:border-purple-500 scale-105'
                                : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600 hover:border-purple-300 dark:hover:border-purple-500 hover:shadow-sm'
                            }
                          `}
                        >
                          <GripVertical className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                            {index + 1}. {getTaskDisplayName(task)}
                          </span>
                          <button
                            onClick={() => removeTask(index)}
                            className="ml-1 p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-colors"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Begin Treatment Button */}
                <button
                  onClick={onStandardQC}
                  disabled={selectedQCTasks.length === 0}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Settings2 className="h-4 w-4" />
                  <span>Begin Treatment</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat Component for QC */}
      {renderStepChat(2)}
    </div>
  );
};

export default Step2DataQC;
