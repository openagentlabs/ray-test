import React, { useState } from 'react';
import { X, Database, Cloud, Server, Eye, EyeOff, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { useDatabase, DatabaseConnection } from '../contexts/DatabaseContext';
import { useData } from '../contexts/DataContext';

interface DatabaseConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionType: 'sql' | 'snowflake' | 'aws_s3' | 'azure_blob';
}

const DatabaseConnectionModal: React.FC<DatabaseConnectionModalProps> = ({
  isOpen,
  onClose,
  connectionType
}) => {
  const { addConnection, testConnection } = useDatabase();
  const { addDataset } = useData();
  const [showPassword, setShowPassword] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string>('');

  const [formData, setFormData] = useState({
    name: '',
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    ssl: false,
    // Snowflake specific
    account: '',
    warehouse: '',
    schema: '',
    // AWS S3 specific
    accessKey: '',
    secretKey: '',
    region: 'us-east-1',
    bucket: '',
    // Azure Blob specific
    connectionString: '',
    containerName: ''
  });

  const handleInputChange = (field: string, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setConnectionStatus('idle');
    setError('');
  };

  const handleTestConnection = async () => {
    setIsConnecting(true);
    setConnectionStatus('testing');
    setError('');

    try {
      const connectionData: Omit<DatabaseConnection, 'id' | 'createdAt'> = {
        name: formData.name,
        type: connectionType,
        status: 'connecting',
        config: getConfigForType(),
      };

      const success = await testConnection(connectionData);
      
      if (success) {
        setConnectionStatus('success');
      } else {
        setConnectionStatus('error');
        setError('Connection failed. Please check your credentials and try again.');
      }
    } catch (err) {
      setConnectionStatus('error');
      setError('An error occurred while testing the connection.');
    } finally {
      setIsConnecting(false);
    }
  };

  const getConfigForType = () => {
    switch (connectionType) {
      case 'sql':
        return {
          host: formData.host,
          port: parseInt(formData.port) || 5432,
          database: formData.database,
          username: formData.username,
          password: formData.password,
          ssl: formData.ssl
        };
      case 'snowflake':
        return {
          account: formData.account,
          username: formData.username,
          password: formData.password,
          database: formData.database,
          warehouse: formData.warehouse,
          schema: formData.schema
        };
      case 'aws_s3':
        return {
          accessKey: formData.accessKey,
          secretKey: formData.secretKey,
          region: formData.region,
          bucket: formData.bucket
        };
      case 'azure_blob':
        return {
          connectionString: formData.connectionString,
          containerName: formData.containerName
        };
      default:
        return {};
    }
  };

  const handleSaveConnection = async () => {
    if (connectionStatus !== 'success') {
      setError('Please test the connection first before saving.');
      return;
    }

    try {
      const connectionId = addConnection({
        name: formData.name,
        type: connectionType,
        status: 'connected',
        config: getConfigForType(),
        lastConnected: new Date()
      });

      // Add as a dataset to the data context
      addDataset({
        name: `${formData.name} (Database)`,
        description: `Connected database • ${connectionType.toUpperCase()}`,
        type: connectionType.toUpperCase(),
        size: 'N/A',
        records: 0,
        lastUpdated: 'Just connected',
        status: 'active',
        data: [],
        columns: []
      });

      onClose();
      setFormData({
        name: '',
        host: '',
        port: '',
        database: '',
        username: '',
        password: '',
        ssl: false,
        account: '',
        warehouse: '',
        schema: '',
        accessKey: '',
        secretKey: '',
        region: 'us-east-1',
        bucket: '',
        connectionString: '',
        containerName: ''
      });
      setConnectionStatus('idle');
    } catch (err) {
      setError('Failed to save connection. Please try again.');
    }
  };

  const getConnectionIcon = () => {
    switch (connectionType) {
      case 'sql':
        return <Database className="h-6 w-6 text-blue-500" />;
      case 'snowflake':
        return <Cloud className="h-6 w-6 text-teal-500" />;
      case 'aws_s3':
        return <Server className="h-6 w-6 text-orange-500" />;
      case 'azure_blob':
        return <Cloud className="h-6 w-6 text-purple-500" />;
      default:
        return <Database className="h-6 w-6 text-gray-500" />;
    }
  };

  const getConnectionTitle = () => {
    switch (connectionType) {
      case 'sql':
        return 'SQL Database Connection';
      case 'snowflake':
        return 'Snowflake Connection';
      case 'aws_s3':
        return 'AWS S3 Connection';
      case 'azure_blob':
        return 'Azure Blob Storage Connection';
      default:
        return 'Database Connection';
    }
  };

  const renderSQLForm = () => (
    <>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Host</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => handleInputChange('host', e.target.value)}
            placeholder="localhost"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Port</label>
          <input
            type="text"
            value={formData.port}
            onChange={(e) => handleInputChange('port', e.target.value)}
            placeholder="5432"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Database</label>
        <input
          type="text"
          value={formData.database}
          onChange={(e) => handleInputChange('database', e.target.value)}
          placeholder="banking_data"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => handleInputChange('username', e.target.value)}
            placeholder="admin"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2"
            >
              {showPassword ? <EyeOff className="h-4 w-4 text-gray-400" /> : <Eye className="h-4 w-4 text-gray-400" />}
            </button>
          </div>
        </div>
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          id="ssl"
          checked={formData.ssl}
          onChange={(e) => handleInputChange('ssl', e.target.checked)}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <label htmlFor="ssl" className="ml-2 text-sm text-gray-700">Use SSL connection</label>
      </div>
    </>
  );

  const renderSnowflakeForm = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Account</label>
        <input
          type="text"
          value={formData.account}
          onChange={(e) => handleInputChange('account', e.target.value)}
          placeholder="myorg-myaccount"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => handleInputChange('username', e.target.value)}
            placeholder="admin"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2"
            >
              {showPassword ? <EyeOff className="h-4 w-4 text-gray-400" /> : <Eye className="h-4 w-4 text-gray-400" />}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Database</label>
          <input
            type="text"
            value={formData.database}
            onChange={(e) => handleInputChange('database', e.target.value)}
            placeholder="BANKING_DB"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Warehouse</label>
          <input
            type="text"
            value={formData.warehouse}
            onChange={(e) => handleInputChange('warehouse', e.target.value)}
            placeholder="COMPUTE_WH"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Schema</label>
          <input
            type="text"
            value={formData.schema}
            onChange={(e) => handleInputChange('schema', e.target.value)}
            placeholder="PUBLIC"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>
    </>
  );

  const renderAWSS3Form = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Access Key ID</label>
        <input
          type="text"
          value={formData.accessKey}
          onChange={(e) => handleInputChange('accessKey', e.target.value)}
          placeholder="AKIAIOSFODNN7EXAMPLE"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Secret Access Key</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={formData.secretKey}
            onChange={(e) => handleInputChange('secretKey', e.target.value)}
            placeholder="••••••••••••••••••••••••••••••••••••••••"
            className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 transform -translate-y-1/2"
          >
            {showPassword ? <EyeOff className="h-4 w-4 text-gray-400" /> : <Eye className="h-4 w-4 text-gray-400" />}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Region</label>
          <select
            value={formData.region}
            onChange={(e) => handleInputChange('region', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            <option value="us-east-1">US East (N. Virginia)</option>
            <option value="us-west-2">US West (Oregon)</option>
            <option value="eu-west-1">Europe (Ireland)</option>
            <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Bucket Name</label>
          <input
            type="text"
            value={formData.bucket}
            onChange={(e) => handleInputChange('bucket', e.target.value)}
            placeholder="my-banking-data"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>
    </>
  );

  const renderAzureBlobForm = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Connection String</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={formData.connectionString}
            onChange={(e) => handleInputChange('connectionString', e.target.value)}
            placeholder="DefaultEndpointsProtocol=https;AccountName=..."
            className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 transform -translate-y-1/2"
          >
            {showPassword ? <EyeOff className="h-4 w-4 text-gray-400" /> : <Eye className="h-4 w-4 text-gray-400" />}
          </button>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Container Name</label>
        <input
          type="text"
          value={formData.containerName}
          onChange={(e) => handleInputChange('containerName', e.target.value)}
          placeholder="banking-data"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
      </div>
    </>
  );

  const renderForm = () => {
    switch (connectionType) {
      case 'sql':
        return renderSQLForm();
      case 'snowflake':
        return renderSnowflakeForm();
      case 'aws_s3':
        return renderAWSS3Form();
      case 'azure_blob':
        return renderAzureBlobForm();
      default:
        return null;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div className="bg-white px-6 pt-6 pb-4">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-3">
                {getConnectionIcon()}
                <h3 className="text-lg font-semibold text-gray-900">{getConnectionTitle()}</h3>
              </div>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Connection Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="My Database Connection"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              {renderForm()}

              {error && (
                <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">{error}</span>
                </div>
              )}

              {connectionStatus === 'success' && (
                <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-3 rounded-lg">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm">Connection successful!</span>
                </div>
              )}
            </div>
          </div>

          <div className="bg-gray-50 px-6 py-4 flex justify-between">
            <button
              onClick={handleTestConnection}
              disabled={isConnecting || !formData.name}
              className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isConnecting ? <Loader className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
              <span>{isConnecting ? 'Testing...' : 'Test Connection'}</span>
            </button>

            <div className="flex space-x-3">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveConnection}
                disabled={connectionStatus !== 'success'}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Connection
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DatabaseConnectionModal; 