import React, { useState, useRef } from 'react';
import { X, Upload, ArrowLeft, Eye, EyeOff } from 'lucide-react';

interface DataSourceModalProps {
  onClose: () => void;
}

interface DataSource {
  id: string;
  name: string;
  icon: string;
  type: 'database' | 'cloud' | 'file';
}

const dataSources: DataSource[] = [
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

const DataSourceModal: React.FC<DataSourceModalProps> = ({ onClose }) => {
  const [currentStep, setCurrentStep] = useState<'main' | 'new-source' | 'configure'>('new-source');
  const [selectedDataSource, setSelectedDataSource] = useState<DataSource | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [configData, setConfigData] = useState({
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    connectionString: '',
    apiKey: '',
    projectId: '',
    dataset: '',
    table: '',
    schema: '',
    warehouse: '',
    account: '',
    region: '',
    accessKey: '',
    secretKey: '',
    spreadsheetId: '',
    sheetName: '',
    baseId: '',
    tableId: '',
    cluster: '',
    databaseName: '',
    collection: '',
    uri: ''
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    // Handle file upload logic here
    console.log('File uploaded:', file.name);
    // You can add file validation, upload to server, etc.
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  const handleDataSourceSelect = (dataSource: DataSource) => {
    setSelectedDataSource(dataSource);
    setCurrentStep('configure');
  };

  const handleConfigChange = (field: string, value: string) => {
    setConfigData(prev => ({ ...prev, [field]: value }));
  };

  const handleConnect = () => {
    console.log('Connecting to:', selectedDataSource?.name, configData);
    // Here you would typically make an API call to establish the connection
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
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="localhost"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Port</label>
          <input
            type="text"
            value={configData.port}
            onChange={(e) => handleConfigChange('port', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="5432"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Database Name</label>
        <input
          type="text"
          value={configData.database}
          onChange={(e) => handleConfigChange('database', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="mydatabase"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
        <input
          type="text"
          value={configData.username}
          onChange={(e) => handleConfigChange('username', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10"
            placeholder="password"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );

  const renderCloudConfig = () => {
    switch (selectedDataSource?.id) {
      case 'google-sheets':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Spreadsheet ID</label>
              <input
                type="text"
                value={configData.spreadsheetId}
                onChange={(e) => handleConfigChange('spreadsheetId', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Sheet Name</label>
              <input
                type="text"
                value={configData.sheetName}
                onChange={(e) => handleConfigChange('sheetName', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Sheet1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
              <input
                type="password"
                value={configData.apiKey}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your Google API key"
              />
            </div>
          </div>
        );
      case 'bigquery':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project ID</label>
              <input
                type="text"
                value={configData.projectId}
                onChange={(e) => handleConfigChange('projectId', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="my-project-id"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Dataset</label>
              <input
                type="text"
                value={configData.dataset}
                onChange={(e) => handleConfigChange('dataset', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="my_dataset"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Table</label>
              <input
                type="text"
                value={configData.table}
                onChange={(e) => handleConfigChange('table', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="my_table"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Service Account Key</label>
              <textarea
                value={configData.apiKey}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Paste your service account JSON key"
                rows={4}
              />
            </div>
          </div>
        );
      case 'snowflake':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account</label>
                <input
                  type="text"
                  value={configData.account}
                  onChange={(e) => handleConfigChange('account', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="your-account.snowflakecomputing.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Warehouse</label>
                <input
                  type="text"
                  value={configData.warehouse}
                  onChange={(e) => handleConfigChange('warehouse', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="SNOWFLAKE_SAMPLE_DATA"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Schema</label>
                <input
                  type="text"
                  value={configData.schema}
                  onChange={(e) => handleConfigChange('schema', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="PUBLIC"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
              <input
                type="text"
                value={configData.username}
                onChange={(e) => handleConfigChange('username', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10"
                  placeholder="password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
        );
      case 'mongodb':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Connection String</label>
              <input
                type="text"
                value={configData.uri}
                onChange={(e) => handleConfigChange('uri', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="mongodb://username:password@host:port/database"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Database Name</label>
              <input
                type="text"
                value={configData.databaseName}
                onChange={(e) => handleConfigChange('databaseName', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="mydatabase"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Collection</label>
              <input
                type="text"
                value={configData.collection}
                onChange={(e) => handleConfigChange('collection', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="mycollection"
              />
            </div>
          </div>
        );
      case 'airtable':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Base ID</label>
              <input
                type="text"
                value={configData.baseId}
                onChange={(e) => handleConfigChange('baseId', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="appXXXXXXXXXXXXXX"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Table ID</label>
              <input
                type="text"
                value={configData.tableId}
                onChange={(e) => handleConfigChange('tableId', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="tblXXXXXXXXXXXXXX"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
              <input
                type="password"
                value={configData.apiKey}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your Airtable API key"
              />
            </div>
          </div>
        );
      default:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">API Key</label>
              <input
                type="password"
                value={configData.apiKey}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your API key"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Region (Optional)</label>
              <input
                type="text"
                value={configData.region}
                onChange={(e) => handleConfigChange('region', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="us-east-1"
              />
            </div>
          </div>
        );
    }
  };

  const renderConfigureStep = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setCurrentStep('new-source')}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Configure {selectedDataSource?.name}</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">Enter your connection details</p>
          </div>
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
      </div>

      {/* Action Buttons */}
      <div className="flex space-x-3 pt-4">
        <button
          onClick={() => setCurrentStep('new-source')}
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
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Database & Cloud Integrations</h3>
          <div className="grid grid-cols-2 gap-3 overflow-y-auto" style={{ height: '260px' }}>
            {dataSources.map((source) => (
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

export default DataSourceModal; 