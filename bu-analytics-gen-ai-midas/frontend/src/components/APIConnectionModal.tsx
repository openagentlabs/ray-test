import React, { useState } from 'react';
import { X, Key, Globe, Shield, Eye, EyeOff, CheckCircle, AlertCircle, Loader, ExternalLink } from 'lucide-react';
import { useDatabase, DatabaseConnection } from '../contexts/DatabaseContext';
import { useData } from '../contexts/DataContext';

interface APIConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiType: 'fred_api' | 'fmp_api' | 'moonshot_api' | 'moodys_api' | 'bloomberg_api' | 'plaid_api' | 'crs_api' | 'creditriskmonitor_api';
}

const APIConnectionModal: React.FC<APIConnectionModalProps> = ({
  isOpen,
  onClose,
  apiType
}) => {
  const { addConnection, testConnection } = useDatabase();
  const { addDataset } = useData();
  const [showApiKey, setShowApiKey] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string>('');

  const [formData, setFormData] = useState({
    name: '',
    apiKey: '',
    apiSecret: '',
    clientId: '',
    clientSecret: '',
    environment: 'sandbox' as 'sandbox' | 'production',
    baseUrl: ''
  });

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setConnectionStatus('idle');
    setError('');
  };

  const getAPIInfo = () => {
    switch (apiType) {
      case 'fred_api':
        return {
          title: 'Federal Reserve Economic Data (FRED)',
          description: 'Access to economic data from the Federal Reserve Bank of St. Louis',
          icon: '🏛️',
          color: 'blue',
          fields: ['apiKey'],
          website: 'https://fred.stlouisfed.org/docs/api/',
          defaultBaseUrl: 'https://api.stlouisfed.org/fred/'
        };
      case 'fmp_api':
        return {
          title: 'Financial Modeling Prep',
          description: 'Real-time and historical financial data, ratios, and analytics',
          icon: '📊',
          color: 'green',
          fields: ['apiKey'],
          website: 'https://financialmodelingprep.com/developer/docs',
          defaultBaseUrl: 'https://financialmodelingprep.com/api/'
        };
      case 'moonshot_api':
        return {
          title: 'Moonshot AI',
          description: 'Advanced AI-powered financial analysis and chat assistance',
          icon: '🌙',
          color: 'purple',
          fields: ['apiKey'],
          website: 'https://platform.moonshot.cn/docs',
          defaultBaseUrl: 'https://api.moonshot.cn/v1/'
        };
      case 'moodys_api':
        return {
          title: 'Moody\'s Analytics',
          description: 'Credit ratings, risk assessment, and economic research data',
          icon: '📈',
          color: 'purple',
          fields: ['apiKey', 'apiSecret'],
          website: 'https://www.moodysanalytics.com/products-and-solutions/data',
          defaultBaseUrl: 'https://api.economy.com/data/'
        };
      case 'bloomberg_api':
        return {
          title: 'Bloomberg Open API',
          description: 'Financial market data, news, and analytics from Bloomberg',
          icon: '💼',
          color: 'orange',
          fields: ['clientId', 'clientSecret'],
          website: 'https://www.bloomberg.com/professional/support/api-library/',
          defaultBaseUrl: 'https://api.bloomberg.com/'
        };
      case 'plaid_api':
        return {
          title: 'Plaid API',
          description: 'Banking and financial account data aggregation',
          icon: '🔗',
          color: 'teal',
          fields: ['clientId', 'clientSecret', 'environment'],
          website: 'https://plaid.com/docs/',
          defaultBaseUrl: 'https://production.plaid.com/'
        };
      case 'crs_api':
        return {
          title: 'CRS Credit API',
          description: 'Credit reporting and risk assessment services',
          icon: '🔍',
          color: 'red',
          fields: ['apiKey', 'apiSecret'],
          website: 'https://www.creditriskservice.com/api',
          defaultBaseUrl: 'https://api.creditriskservice.com/'
        };
      case 'creditriskmonitor_api':
        return {
          title: 'CreditRiskMonitor API',
          description: 'Commercial credit risk monitoring and financial analysis',
          icon: '⚠️',
          color: 'yellow',
          fields: ['apiKey', 'clientId'],
          website: 'https://www.creditriskmonitor.com/api',
          defaultBaseUrl: 'https://api.creditriskmonitor.com/'
        };
      default:
        return {
          title: 'API Connection',
          description: 'Connect to external API',
          icon: '🔌',
          color: 'gray',
          fields: ['apiKey'],
          website: '#',
          defaultBaseUrl: ''
        };
    }
  };

  const apiInfo = getAPIInfo();

  const handleTestConnection = async () => {
    setIsConnecting(true);
    setConnectionStatus('testing');
    setError('');

    try {
      const connectionData: Omit<DatabaseConnection, 'id' | 'createdAt'> = {
        name: formData.name,
        type: apiType,
        status: 'connecting',
        config: {
          ...formData,
          baseUrl: formData.baseUrl || apiInfo.defaultBaseUrl
        },
      };

      const success = await testConnection(connectionData);
      
      if (success) {
        setConnectionStatus('success');
      } else {
        setConnectionStatus('error');
        setError('API connection failed. Please check your credentials and try again.');
      }
    } catch (err) {
      setConnectionStatus('error');
      setError('An error occurred while testing the API connection.');
    } finally {
      setIsConnecting(false);
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
        type: apiType,
        status: 'connected',
        config: {
          ...formData,
          baseUrl: formData.baseUrl || apiInfo.defaultBaseUrl
        },
        lastConnected: new Date()
      });

      // Add as a dataset to the data context
      addDataset({
        name: `${formData.name} (API)`,
        description: `Connected API • ${apiInfo.title}`,
        type: 'API',
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
        apiKey: '',
        apiSecret: '',
        clientId: '',
        clientSecret: '',
        environment: 'sandbox',
        baseUrl: ''
      });
      setConnectionStatus('idle');
    } catch (err) {
      setError('Failed to save API connection. Please try again.');
    }
  };

  const renderFormFields = () => {
    const fields = apiInfo.fields;
    
    return (
      <div className="space-y-4">
        {fields.includes('apiKey') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.apiKey}
                onChange={(e) => handleInputChange('apiKey', e.target.value)}
                placeholder="Enter your API key"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2"
              >
                {showApiKey ? <EyeOff className="h-4 w-4 text-gray-400" /> : <Eye className="h-4 w-4 text-gray-400" />}
              </button>
            </div>
          </div>
        )}

        {fields.includes('apiSecret') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">API Secret</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.apiSecret}
                onChange={(e) => handleInputChange('apiSecret', e.target.value)}
                placeholder="Enter your API secret"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>
        )}

        {fields.includes('clientId') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Client ID</label>
            <input
              type="text"
              value={formData.clientId}
              onChange={(e) => handleInputChange('clientId', e.target.value)}
              placeholder="Enter your client ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
        )}

        {fields.includes('clientSecret') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Client Secret</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.clientSecret}
                onChange={(e) => handleInputChange('clientSecret', e.target.value)}
                placeholder="Enter your client secret"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>
        )}

        {fields.includes('environment') && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Environment</label>
            <select
              value={formData.environment}
              onChange={(e) => handleInputChange('environment', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              <option value="sandbox">Sandbox</option>
              <option value="production">Production</option>
            </select>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Base URL (Optional)</label>
          <input
            type="url"
            value={formData.baseUrl}
            onChange={(e) => handleInputChange('baseUrl', e.target.value)}
            placeholder={apiInfo.defaultBaseUrl}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>
    );
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
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-2xl ${
                  apiInfo.color === 'blue' ? 'bg-blue-100' :
                  apiInfo.color === 'green' ? 'bg-green-100' :
                  apiInfo.color === 'purple' ? 'bg-purple-100' :
                  apiInfo.color === 'orange' ? 'bg-orange-100' :
                  apiInfo.color === 'teal' ? 'bg-teal-100' :
                  apiInfo.color === 'red' ? 'bg-red-100' :
                  apiInfo.color === 'yellow' ? 'bg-yellow-100' :
                  'bg-gray-100'
                }`}>
                  {apiInfo.icon}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{apiInfo.title}</h3>
                  <p className="text-sm text-gray-600">{apiInfo.description}</p>
                </div>
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
                  placeholder={`My ${apiInfo.title} Connection`}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              {renderFormFields()}

              <div className="bg-blue-50 p-3 rounded-lg">
                <div className="flex items-center space-x-2">
                  <ExternalLink className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium text-blue-900">Need API credentials?</span>
                </div>
                <p className="text-sm text-blue-700 mt-1">
                  Visit the{' '}
                  <a 
                    href={apiInfo.website} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="underline hover:text-blue-800"
                  >
                    {apiInfo.title} documentation
                  </a>
                  {' '}to obtain your API credentials.
                </p>
              </div>

              {error && (
                <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">{error}</span>
                </div>
              )}

              {connectionStatus === 'success' && (
                <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-3 rounded-lg">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm">API connection successful!</span>
                </div>
              )}
            </div>
          </div>

          <div className="bg-gray-50 px-6 py-4 flex justify-between">
            <button
              onClick={handleTestConnection}
              disabled={isConnecting || !formData.name || (!formData.apiKey && !formData.clientId)}
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

export default APIConnectionModal; 