// DataSplit: Shows read-only partition info for Steps 2-9
// The actual split configuration is handled by PlatformPartitionSection in Step 1

import React, { useState, useEffect } from 'react';

interface DataSplitProps {
  activeDatasetId?: string | null;
  datasetAnalysis?: {
    totalRows: number;
    columns: any[];
  } | null;
  mode?: 'step1' | 'other';
  stepKey?: string | number;
  selectedDataSources?: any[];
  showSamplingUI?: boolean;
  showLockedInfo?: boolean;
  onScopeChange?: (scope: 'train' | 'test' | 'validation') => void;
  selectedScope?: 'train' | 'test' | 'validation';
}

const DataSplit: React.FC<DataSplitProps> = ({
  datasetAnalysis,
  mode = 'other',
  showLockedInfo = true,
  onScopeChange,
  selectedScope: externalScope,
}) => {
  // Read split configuration from sessionStorage
  const getSplitConfig = () => {
    try {
      const raw = sessionStorage.getItem('dataset_config');
      if (!raw) return null;
      const cfg = JSON.parse(raw);
      return cfg.split_configuration || null;
    } catch {
      return null;
    }
  };

  const [splitConfig, setSplitConfig] = useState(getSplitConfig);
  const [internalScope, setInternalScope] = useState<'train' | 'test' | 'validation'>('train');
  
  const selectedScope = externalScope ?? internalScope;

  useEffect(() => {
    setSplitConfig(getSplitConfig());
  }, [mode]);

  // Don't render in Step 1 - PlatformPartitionSection handles that
  if (mode === 'step1') {
    return null;
  }

  // For Steps 2-9: show read-only partition info
  if (!showLockedInfo || !splitConfig) {
    return null;
  }

  const ratios = splitConfig.ratios || { train: 60, test: 20, validation: 20 };
  const method = splitConfig.split_method || 'stratified_random';
  const methodLabel = method === 'user_identifier' 
    ? 'User identifier' 
    : method === 'time_based' 
      ? 'Time-based' 
      : 'Stratified random';

  const totalRows = datasetAnalysis?.totalRows || 0;
  const trainRows = Math.round(totalRows * ratios.train / 100);
  const testRows = Math.round(totalRows * ratios.test / 100);
  const validationRows = Math.round(totalRows * ratios.validation / 100);

  const handleScopeChange = (scope: 'train' | 'test' | 'validation') => {
    setInternalScope(scope);
    if (onScopeChange) {
      onScopeChange(scope);
    }
  };

  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
      <div className="text-sm text-gray-600 mb-2">
        <span className="font-medium">Data partition:</span> {methodLabel}
      </div>
      <div className="flex items-center gap-6 text-xs text-gray-500">
        <label className="flex items-center gap-2 cursor-default">
          <input
            type="radio"
            name="dataPartition"
            value="train"
            checked={selectedScope === 'train'}
            onChange={() => handleScopeChange('train')}
            disabled
            className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 opacity-70"
          />
          <span>
            <span className="font-medium text-blue-600">Train:</span> {ratios.train}% ({trainRows.toLocaleString()} rows)
          </span>
        </label>
        <label className="flex items-center gap-2 cursor-default">
          <input
            type="radio"
            name="dataPartition"
            value="test"
            checked={selectedScope === 'test'}
            onChange={() => handleScopeChange('test')}
            disabled
            className="w-4 h-4 text-green-600 border-gray-300 focus:ring-green-500 opacity-70"
          />
          <span>
            <span className="font-medium text-green-600">Test:</span> {ratios.test}% ({testRows.toLocaleString()} rows)
          </span>
        </label>
        <label className="flex items-center gap-2 cursor-default">
          <input
            type="radio"
            name="dataPartition"
            value="validation"
            checked={selectedScope === 'validation'}
            onChange={() => handleScopeChange('validation')}
            disabled
            className="w-4 h-4 text-amber-600 border-gray-300 focus:ring-amber-500 opacity-70"
          />
          <span>
            <span className="font-medium text-amber-600">Validation:</span> {ratios.validation}% ({validationRows.toLocaleString()} rows)
          </span>
        </label>
      </div>
    </div>
  );
};

export default DataSplit;
