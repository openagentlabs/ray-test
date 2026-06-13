import React, { useState, useRef } from 'react';
import { Database, FileText, ArrowRight, CheckCircle, X, Upload, Eye, EyeOff } from 'lucide-react';
import { INTEGRATION_DATA_SOURCES, IntegrationDataSource, getConnectionStrategy } from '../components/DataSourceSelection';

// ============================================================================
// OOP: Domain Types (Encapsulation - types define the shape of data)
// ============================================================================

type IngestionItemKind = 'file' | 'database' | 'cloud';

interface BaseIngestionItem {
  id: string;
  kind: IngestionItemKind;
  createdAt: Date;
}

interface FileIngestionItem extends BaseIngestionItem {
  kind: 'file';
  file: File;
}

interface IntegrationIngestionItem extends BaseIngestionItem {
  kind: 'database' | 'cloud';
  sourceId: string;
  sourceName: string;
  sourceIcon: string;
  config: Record<string, string>;
}

type IngestionItem = FileIngestionItem | IntegrationIngestionItem;

// ============================================================================
// OOP: Behavior Functions (Encapsulated with Domain Types)
// ============================================================================

function generateIngestionId(): string {
  return `ing-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getDisplayName(item: IngestionItem): string {
  switch (item.kind) {
    case 'file':
      return item.file.name;
    case 'database':
    case 'cloud':
      return item.sourceName;
  }
}

function getSummaryLine(item: IngestionItem): string {
  switch (item.kind) {
    case 'file':
      return `File Upload (${formatBytes(item.file.size)})`;
    case 'database':
      return 'Database Connection';
    case 'cloud':
      return 'Cloud Service Connection';
  }
}

function isFileItem(item: IngestionItem): item is FileIngestionItem {
  return item.kind === 'file';
}

function removeItemById(items: IngestionItem[], id: string): IngestionItem[] {
  return items.filter(item => item.id !== id);
}

// ============================================================================
// Component
// ============================================================================

const DataIngestion: React.FC = () => {
  const [selectedDataSources, setSelectedDataSources] = useState<IngestionItem[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<IntegrationDataSource | null>(null);
  const [configData, setConfigData] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [showPassword, setShowPassword] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // File upload handlers
  const handleFileUpload = (file: File) => {
    const item: FileIngestionItem = {
      id: generateIngestionId(),
      kind: 'file',
      createdAt: new Date(),
      file,
    };
    setSelectedDataSources(prev => [...prev, item]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  // Integration selection handlers
  const handleIntegrationSelect = (source: IntegrationDataSource) => {
    if (selectedIntegration?.id === source.id) {
      setSelectedIntegration(null);
      setConfigData({});
      setValidationErrors([]);
      return;
    }
    setSelectedIntegration(source);
    const strategy = getConnectionStrategy(source.id);
    setConfigData(strategy.getInitialConfig());
    setValidationErrors([]);
  };

  const handleConfigChange = (field: string, value: string) => {
    setConfigData(prev => ({ ...prev, [field]: value }));
    setValidationErrors([]);
  };

  const handleConnect = () => {
    if (!selectedIntegration) return;
    
    const strategy = getConnectionStrategy(selectedIntegration.id);
    const validation = strategy.validate(configData);
    
    if (!validation.valid) {
      setValidationErrors(validation.errors);
      return;
    }
    
    const sourceType = selectedIntegration.type === 'database' ? 'database' : 'cloud';
    const item: IntegrationIngestionItem = {
      id: generateIngestionId(),
      kind: sourceType,
      createdAt: new Date(),
      sourceId: selectedIntegration.id,
      sourceName: selectedIntegration.name,
      sourceIcon: selectedIntegration.icon,
      config: configData,
    };
    setSelectedDataSources(prev => [...prev, item]);
    setSelectedIntegration(null);
    setConfigData({});
    setValidationErrors([]);
  };

  const handleCancelConfig = () => {
    setSelectedIntegration(null);
    setConfigData({});
    setValidationErrors([]);
  };

  const handleRemoveDataSource = (id: string) => {
    setSelectedDataSources(prev => removeItemById(prev, id));
  };

  // Render database config form
  const renderDatabaseConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Host</label>
          <input
            type="text"
            value={configData.host || ''}
            onChange={(e) => handleConfigChange('host', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="localhost"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Port</label>
          <input
            type="text"
            value={configData.port || ''}
            onChange={(e) => handleConfigChange('port', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="5432"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Database</label>
        <input
          type="text"
          value={configData.database || ''}
          onChange={(e) => handleConfigChange('database', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="mydatabase"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
          <input
            type="text"
            value={configData.username || ''}
            onChange={(e) => handleConfigChange('username', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="username"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={configData.password || ''}
              onChange={(e) => handleConfigChange('password', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-10"
              placeholder="password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // Render cloud config form
  const renderCloudConfig = () => {
    const source = selectedIntegration?.id;
    
    if (source === 'google-sheets') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Spreadsheet ID</label>
            <input
              type="text"
              value={configData.spreadsheetId || ''}
              onChange={(e) => handleConfigChange('spreadsheetId', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Sheet Name</label>
            <input
              type="text"
              value={configData.sheetName || ''}
              onChange={(e) => handleConfigChange('sheetName', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Sheet1"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
            <input
              type="password"
              value={configData.apiKey || ''}
              onChange={(e) => handleConfigChange('apiKey', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="AIzaSy..."
            />
          </div>
        </div>
      );
    }
    
    if (source === 'bigquery') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project ID</label>
            <input
              type="text"
              value={configData.projectId || ''}
              onChange={(e) => handleConfigChange('projectId', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="my-project-123"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Dataset</label>
            <input
              type="text"
              value={configData.dataset || ''}
              onChange={(e) => handleConfigChange('dataset', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="my_dataset"
            />
          </div>
        </div>
      );
    }
    
    // Default cloud config
    return (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Connection String</label>
          <input
            type="text"
            value={configData.connectionString || ''}
            onChange={(e) => handleConfigChange('connectionString', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter connection string..."
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
          <input
            type="password"
            value={configData.apiKey || ''}
            onChange={(e) => handleConfigChange('apiKey', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter API key..."
          />
        </div>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Data Sources</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">Select your data sources for model training. Upload files, connect to APIs, or choose from available datasets.</p>
      </div>

      {/* Data Source Selection - Embedded directly on page */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
        <div className="grid grid-cols-2 gap-6">
          {/* Local File Upload */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Local File Upload</h3>
            <div
              className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                dragActive ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <Upload className="h-8 w-8 text-gray-400 dark:text-gray-500 mx-auto mb-3" />
              <p className="text-gray-600 dark:text-gray-400 mb-2 text-sm">
                Drag and drop files here, or{' '}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-blue-600 hover:text-blue-700 font-medium"
                >
                  browse files
                </button>
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                CSV files only
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".csv"
              onChange={handleFileSelect}
            />
          </div>

          {/* Database & Cloud Integrations */}
          <div className="space-y-4">
            {/* Show grid only when no integration is selected */}
            {!selectedIntegration ? (
              <>
                <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Database & Cloud Integrations</h3>
                <div className="grid grid-cols-2 gap-3 overflow-y-auto" style={{ maxHeight: '260px' }}>
                  {INTEGRATION_DATA_SOURCES.map((source) => (
                    <button
                      key={source.id}
                      onClick={() => handleIntegrationSelect(source)}
                      className="p-3 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition text-left h-14"
                    >
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">{source.icon}</span>
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          {source.name}
                        </span>
                      </div>
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
                    onClick={handleCancelConfig}
                    className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition"
                  >
                    <X className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                  </button>
                </div>
                
                {selectedIntegration.type === 'database' ? renderDatabaseConfig() : renderCloudConfig()}
                
                {validationErrors.length > 0 && (
                  <div className="mt-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                    <p className="text-xs font-medium text-red-800 dark:text-red-200 mb-1">Please fix the following:</p>
                    <ul className="list-disc list-inside text-xs text-red-700 dark:text-red-300 space-y-0.5">
                      {validationErrors.map((error, index) => (
                        <li key={index}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                <div className="flex space-x-3 mt-4 pt-3 border-t border-gray-200 dark:border-gray-600">
                  <button
                    onClick={handleCancelConfig}
                    className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConnect}
                    className="px-4 py-2 text-sm bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition font-medium"
                  >
                    Connect
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Selected Data Sources */}
      {selectedDataSources.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Selected Data Sources</h3>
          <div className="space-y-3">
            {selectedDataSources.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                <div className="flex items-center space-x-3">
                  {isFileItem(item) ? (
                    <FileText className="h-5 w-5 text-blue-500" />
                  ) : (
                    <Database className="h-5 w-5 text-green-500" />
                  )}
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100">
                      {getDisplayName(item)}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {getSummaryLine(item)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <button
                    onClick={() => handleRemoveDataSource(item.id)}
                    className="p-1 hover:bg-red-100 rounded text-red-500 hover:text-red-700 transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          <div className="mt-6 flex items-center justify-between">
            <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>{selectedDataSources.length} data source{selectedDataSources.length !== 1 ? 's' : ''} selected</span>
            </div>
            <button className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center space-x-2">
              <span>Continue to Model Training</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataIngestion;
