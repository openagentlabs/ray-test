import React, { useState, useRef } from 'react';
import { X, Upload, ArrowLeft, Eye, EyeOff } from 'lucide-react';

// ============================================================================
// OOP: Domain Types
// ============================================================================

export interface IntegrationDataSource {
  id: string;
  name: string;
  icon: string;
  type: 'database' | 'cloud' | 'file';
}

export const INTEGRATION_DATA_SOURCES: IntegrationDataSource[] = [
  { id: 'google-sheets', name: 'Google Sheets', icon: '📊', type: 'cloud' },
  { id: 'postgresql', name: 'PostgreSQL', icon: '🐘', type: 'database' },
  { id: 'mysql', name: 'MySQL', icon: '🐬', type: 'database' },
  { id: 'redshift', name: 'Redshift', icon: '🔴', type: 'database' },
  { id: 'bigquery', name: 'Google BigQuery', icon: '🔍', type: 'cloud' },
  { id: 'athena', name: 'Amazon Athena', icon: '🏛️', type: 'cloud' },
  { id: 'sqlserver', name: 'Microsoft SQL Server', icon: '💾', type: 'database' },
  { id: 'mariadb', name: 'MariaDB', icon: '🌊', type: 'database' },
  { id: 'oracle', name: 'Oracle Database', icon: '🏢', type: 'database' },
  { id: 'snowflake', name: 'Snowflake', icon: '❄️', type: 'cloud' },
  { id: 'motherduck', name: 'MotherDuck', icon: '🦆', type: 'cloud' },
  { id: 'databricks', name: 'Databricks', icon: '🧱', type: 'cloud' },
  { id: 'mongodb', name: 'MongoDB', icon: '🍃', type: 'database' },
  { id: 'airtable', name: 'Airtable', icon: '📋', type: 'cloud' },
];

// ============================================================================
// OOP: Strategy Pattern Interface (Open/Closed Principle)
// Each strategy encapsulates config, required fields, and validation
// Add new sources by adding strategies - no changes to existing code
// ============================================================================

interface ValidationResult {
  valid: boolean;
  errors: string[];
}

interface ConnectionStrategy {
  getInitialConfig(): Record<string, string>;
  getRequiredFields(): string[];
  validate(config: Record<string, string>): ValidationResult;
}

// ============================================================================
// OOP: Strategy Implementations (Single Responsibility - one per source)
// ============================================================================

const databaseStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({
    host: '', port: '5432', database: '', username: '', password: '', connectionString: '',
  }),
  getRequiredFields: () => ['host', 'database', 'username', 'password'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.host?.trim()) errors.push('Host is required');
    if (!config.database?.trim()) errors.push('Database is required');
    if (!config.username?.trim()) errors.push('Username is required');
    if (!config.password?.trim()) errors.push('Password is required');
    return { valid: errors.length === 0, errors };
  },
};

const mysqlStrategy: ConnectionStrategy = {
  ...databaseStrategy,
  getInitialConfig: () => ({ host: '', port: '3306', database: '', username: '', password: '' }),
};

const sqlServerStrategy: ConnectionStrategy = {
  ...databaseStrategy,
  getInitialConfig: () => ({ host: '', port: '1433', database: '', username: '', password: '', schema: 'dbo' }),
};

const redshiftStrategy: ConnectionStrategy = {
  ...databaseStrategy,
  getInitialConfig: () => ({ host: '', port: '5439', database: '', username: '', password: '', schema: 'public' }),
};

const mongodbStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ uri: '', databaseName: '', collection: '' }),
  getRequiredFields: () => ['uri', 'databaseName'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.uri?.trim()) errors.push('Connection URI is required');
    if (!config.databaseName?.trim()) errors.push('Database name is required');
    return { valid: errors.length === 0, errors };
  },
};

const googleSheetsStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ spreadsheetId: '', sheetName: '', apiKey: '' }),
  getRequiredFields: () => ['spreadsheetId'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.spreadsheetId?.trim()) errors.push('Spreadsheet ID is required');
    return { valid: errors.length === 0, errors };
  },
};

const bigQueryStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ projectId: '', dataset: '', table: '', apiKey: '' }),
  getRequiredFields: () => ['projectId', 'dataset'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.projectId?.trim()) errors.push('Project ID is required');
    if (!config.dataset?.trim()) errors.push('Dataset is required');
    return { valid: errors.length === 0, errors };
  },
};

const snowflakeStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ account: '', warehouse: '', database: '', schema: 'PUBLIC', username: '', password: '' }),
  getRequiredFields: () => ['account', 'warehouse', 'database', 'username', 'password'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.account?.trim()) errors.push('Account is required');
    if (!config.warehouse?.trim()) errors.push('Warehouse is required');
    if (!config.database?.trim()) errors.push('Database is required');
    if (!config.username?.trim()) errors.push('Username is required');
    if (!config.password?.trim()) errors.push('Password is required');
    return { valid: errors.length === 0, errors };
  },
};

const athenaStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ region: '', database: '', s3OutputLocation: '', accessKey: '', secretKey: '' }),
  getRequiredFields: () => ['region', 'database'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.region?.trim()) errors.push('AWS Region is required');
    if (!config.database?.trim()) errors.push('Database is required');
    return { valid: errors.length === 0, errors };
  },
};

const databricksStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ host: '', httpPath: '', accessToken: '', catalog: '', schema: 'default' }),
  getRequiredFields: () => ['host', 'httpPath', 'accessToken'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.host?.trim()) errors.push('Server hostname is required');
    if (!config.httpPath?.trim()) errors.push('HTTP Path is required');
    if (!config.accessToken?.trim()) errors.push('Access Token is required');
    return { valid: errors.length === 0, errors };
  },
};

const airtableStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ baseId: '', tableId: '', apiKey: '' }),
  getRequiredFields: () => ['baseId', 'tableId', 'apiKey'],
  validate: (config) => {
    const errors: string[] = [];
    if (!config.baseId?.trim()) errors.push('Base ID is required');
    if (!config.tableId?.trim()) errors.push('Table ID is required');
    if (!config.apiKey?.trim()) errors.push('API Key is required');
    return { valid: errors.length === 0, errors };
  },
};

const defaultStrategy: ConnectionStrategy = {
  getInitialConfig: () => ({ host: '', port: '', database: '', username: '', password: '', connectionString: '', apiKey: '' }),
  getRequiredFields: () => [],
  validate: () => ({ valid: true, errors: [] }),
};

// ============================================================================
// OOP: Strategy Registry (Open/Closed - add new sources here only)
// ============================================================================

const connectionStrategies: Record<string, ConnectionStrategy> = {
  'postgresql': databaseStrategy,
  'mysql': mysqlStrategy,
  'mariadb': mysqlStrategy,
  'sqlserver': sqlServerStrategy,
  'oracle': databaseStrategy,
  'redshift': redshiftStrategy,
  'mongodb': mongodbStrategy,
  'google-sheets': googleSheetsStrategy,
  'bigquery': bigQueryStrategy,
  'snowflake': snowflakeStrategy,
  'athena': athenaStrategy,
  'databricks': databricksStrategy,
  'airtable': airtableStrategy,
  'motherduck': defaultStrategy,
};

export function getConnectionStrategy(sourceId: string): ConnectionStrategy {
  return connectionStrategies[sourceId] || defaultStrategy;
}

// ============================================================================
// Component
// ============================================================================

interface DataSourceSelectionProps {
  onClose: () => void;
  onDataSourceSelect?: (dataSource: {
    type: string;
    file?: File;
    ingestionId?: string;
    source?: IntegrationDataSource;
    config?: Record<string, string>;
  }) => void;
}

const DataSourceSelection: React.FC<DataSourceSelectionProps> = ({ onClose, onDataSourceSelect }) => {
  const [currentStep, setCurrentStep] = useState<'main' | 'new-source' | 'configure'>('new-source');
  const [selectedDataSource, setSelectedDataSource] = useState<IntegrationDataSource | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  
  // OOP: Config initialized from strategy when source is selected (not a giant fixed object)
  const [configData, setConfigData] = useState<Record<string, string>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isHandlingFileSelectionRef = useRef(false);

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

  const handleFileUpload = (file: File) => {
    if (onDataSourceSelect) {
      const ingestionId = `ing-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
      onDataSourceSelect({ type: 'file', file, ingestionId });
    }
    // Close modal immediately after file selection for deterministic UX in Safari.
    onClose();
    setTimeout(() => {
      isHandlingFileSelectionRef.current = false;
    }, 0);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      handleFileUpload(selectedFile);
    }
    // Allow selecting the same file repeatedly (important for Safari retry flows)
    e.target.value = '';
  };

  const handleFileInput = (e: React.FormEvent<HTMLInputElement>) => {
    const target = e.currentTarget;
    const selectedFile = target.files?.[0];
    if (selectedFile) {
      handleFileUpload(selectedFile);
    }
  };

  // OOP: Initialize config from strategy when source is selected (Encapsulation)
  const handleDataSourceSelect = (dataSource: IntegrationDataSource) => {
    setSelectedDataSource(dataSource);
    const strategy = getConnectionStrategy(dataSource.id);
    setConfigData(strategy.getInitialConfig());
    setValidationErrors([]);
    setCurrentStep('configure');
  };

  const handleConfigChange = (field: string, value: string) => {
    setConfigData(prev => ({ ...prev, [field]: value }));
    setValidationErrors([]);
  };

  // OOP: Validate using strategy before connecting (Single Responsibility)
  const handleConnect = () => {
    if (!selectedDataSource) return;
    
    const strategy = getConnectionStrategy(selectedDataSource.id);
    const validation = strategy.validate(configData);
    
    if (!validation.valid) {
      setValidationErrors(validation.errors);
      return;
    }
    
    console.log('Connecting to:', selectedDataSource.name, configData);
    if (onDataSourceSelect) {
      onDataSourceSelect({ 
        type: selectedDataSource.type, 
        source: selectedDataSource, 
        config: configData 
      });
    }
    onClose();
  };

  const renderDatabaseConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Host</label>
          <input
            type="text"
            value={configData.host}
            onChange={(e) => handleConfigChange('host', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="localhost"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Port</label>
          <input
            type="text"
            value={configData.port}
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
          value={configData.database}
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
            value={configData.username}
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
              value={configData.password}
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
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Connection String (Optional)</label>
        <input
          type="text"
          value={configData.connectionString}
          onChange={(e) => handleConfigChange('connectionString', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="postgresql://username:password@host:port/database"
        />
      </div>
    </div>
  );

  const renderCloudConfig = () => {
    const source = selectedDataSource?.id;
    
    if (source === 'google-sheets') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Spreadsheet ID</label>
            <input
              type="text"
              value={configData.spreadsheetId}
              onChange={(e) => handleConfigChange('spreadsheetId', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Sheet Name</label>
            <input
              type="text"
              value={configData.sheetName}
              onChange={(e) => handleConfigChange('sheetName', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Sheet1"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
            <input
              type="password"
              value={configData.apiKey}
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
              value={configData.projectId}
              onChange={(e) => handleConfigChange('projectId', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="my-project-123"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Dataset</label>
              <input
                type="text"
                value={configData.dataset}
                onChange={(e) => handleConfigChange('dataset', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="my_dataset"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Table</label>
              <input
                type="text"
                value={configData.table}
                onChange={(e) => handleConfigChange('table', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="my_table"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Service Account Key</label>
            <textarea
              value={configData.apiKey}
              onChange={(e) => handleConfigChange('apiKey', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={4}
              placeholder="Paste your service account JSON key here..."
            />
          </div>
        </div>
      );
    }
    
    if (source === 'snowflake') {
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account</label>
              <input
                type="text"
                value={configData.account}
                onChange={(e) => handleConfigChange('account', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="your-account.snowflakecomputing.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Warehouse</label>
              <input
                type="text"
                value={configData.warehouse}
                onChange={(e) => handleConfigChange('warehouse', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="COMPUTE_WH"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Database</label>
              <input
                type="text"
                value={configData.database}
                onChange={(e) => handleConfigChange('database', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="SNOWFLAKE_SAMPLE_DATA"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Schema</label>
              <input
                type="text"
                value={configData.schema}
                onChange={(e) => handleConfigChange('schema', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="TPCH_SF1"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
              <input
                type="text"
                value={configData.username}
                onChange={(e) => handleConfigChange('username', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={configData.password}
                onChange={(e) => handleConfigChange('password', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="password"
              />
            </div>
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
            value={configData.connectionString}
            onChange={(e) => handleConfigChange('connectionString', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter connection string..."
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
          <input
            type="password"
            value={configData.apiKey}
            onChange={(e) => handleConfigChange('apiKey', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter API key..."
          />
        </div>
      </div>
    );
  };

  const renderConfigureStep = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              setCurrentStep('new-source');
              setValidationErrors([]);
            }}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Configure {selectedDataSource?.name}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
        >
          <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
      </div>

      {/* Configuration Form */}
      <div className="space-y-6">
        {selectedDataSource?.type === 'database' ? renderDatabaseConfig() : renderCloudConfig()}
        
        {/* OOP: Display validation errors from strategy */}
        {validationErrors.length > 0 && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm font-medium text-red-800 dark:text-red-200 mb-2">Please fix the following errors:</p>
            <ul className="list-disc list-inside text-sm text-red-700 dark:text-red-300 space-y-1">
              {validationErrors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </div>
        )}
        
        <div className="flex space-x-3 pt-4">
          <button
            onClick={() => {
              setCurrentStep('new-source');
              setValidationErrors([]);
            }}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
          >
            Back
          </button>
          <button
            onClick={handleConnect}
            className="px-6 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition font-medium"
          >
            Connect
          </button>
        </div>
      </div>
    </div>
  );

  const renderNewDataSourceStep = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">New Data Source</h2>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
        >
          <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
      </div>

      {/* Two Column Layout */}
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
              <label
                htmlFor="local-csv-upload-input"
                className="text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
              >
                browse files
              </label>
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              CSV files only
            </p>
          </div>
          <input
            id="local-csv-upload-input"
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".csv,text/csv,application/vnd.ms-excel"
            onChange={handleFileSelect}
            onInput={handleFileInput}
          />
        </div>

        {/* Database & Cloud Integrations */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Database & Cloud Integrations</h3>
          <div className="grid grid-cols-2 gap-3 overflow-y-auto" style={{ height: '260px' }}>
            {INTEGRATION_DATA_SOURCES.map((source) => (
              <button
                key={source.id}
                onClick={() => handleDataSourceSelect(source)}
                className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition text-left h-14"
              >
                <div className="flex items-center space-x-2">
                  <span className="text-lg">{source.icon}</span>
                  <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{source.name}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {currentStep === 'new-source' && renderNewDataSourceStep()}
          {currentStep === 'configure' && renderConfigureStep()}
        </div>
      </div>
    </div>
  );
};

export default DataSourceSelection; 
