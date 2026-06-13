import React, { useState } from 'react';
import { TrendingUp, Database, Cloud, RefreshCw, Plus, Settings, BarChart3, DollarSign, Globe, Activity } from 'lucide-react';
import FREDIntegration from '../components/FREDIntegration';
import FMPIntegration from '../components/FMPIntegration';

const APIDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'fred' | 'fmp'>('overview');

  const apiServices = [
    {
      id: 'fred',
      name: 'Federal Reserve Economic Data (FRED)',
      description: 'Access to 820,000+ economic data series from the Federal Reserve',
      icon: Database,
      color: 'blue',
      status: 'active',
      dataTypes: ['GDP', 'Unemployment', 'Inflation', 'Interest Rates', 'Housing Data'],
      lastUpdated: 'Real-time'
    },
    {
      id: 'fmp',
      name: 'Financial Modeling Prep (FMP)',
      description: 'Real-time financial market data, ratios, and analytics',
      icon: TrendingUp,
      color: 'green',
      status: 'active',
      dataTypes: ['Stock Prices', 'Company Profiles', 'Financial Ratios', 'Market Data', 'Historical Charts'],
      lastUpdated: 'Real-time'
    }
  ];

  const renderOverview = () => (
    <div className="space-y-8">
      {/* API Services Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {apiServices.map((service) => (
          <div key={service.id} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                  service.color === 'blue' ? 'bg-blue-100 text-blue-600' : 
                  service.color === 'green' ? 'bg-green-100 text-green-600' : 
                  service.color === 'purple' ? 'bg-purple-100 text-purple-600' :
                  service.color === 'indigo' ? 'bg-indigo-100 text-indigo-600' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  <service.icon className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{service.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{service.description}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-green-600 font-medium">{service.status.toUpperCase()}</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Available Data Types</h4>
                <div className="flex flex-wrap gap-2">
                  {service.dataTypes.map((type, index) => (
                    <span key={index} className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs rounded">
                      {type}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-gray-500 dark:text-gray-400">Last Updated: {service.lastUpdated}</span>
                <button
                  onClick={() => setActiveTab(service.id as 'fred' | 'fmp')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                    service.color === 'blue' 
                      ? 'bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-blue-700 dark:hover:bg-[#333380]' 
                      : 'bg-green-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-green-700 dark:hover:bg-[#333380]'
                  }`}
                >
                  Access Data
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-2">
            <Globe className="h-5 w-5 text-blue-600" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Economic Series</span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1">820K+</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">FRED Database</div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-2">
            <DollarSign className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Market Data</span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1">Real-time</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">FMP API</div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-purple-600" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Data Sources</span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1">3</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Active APIs</div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-2">
            <RefreshCw className="h-5 w-5 text-orange-600" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Update Frequency</span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1">Live</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Continuous</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">API Information</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <div className="flex items-center space-x-3">
              <Database className="h-5 w-5 text-blue-600" />
              <div>
                <div className="font-medium text-gray-900 dark:text-gray-100">FRED API</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Federal Reserve Economic Data</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-blue-600">Active</div>
              <div className="text-xs text-gray-500">Economic indicators available</div>
            </div>
          </div>

          <div className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <div className="flex items-center space-x-3">
              <TrendingUp className="h-5 w-5 text-green-600" />
              <div>
                <div className="font-medium text-gray-900 dark:text-gray-100">FMP API</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Financial Modeling Prep</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-green-600">Active</div>
              <div className="text-xs text-gray-500">Market data available</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">API Dashboard</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Access and analyze data from financial and economic APIs
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <div className="flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'overview'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('fred')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'fred'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            FRED Economic Data
          </button>
          <button
            onClick={() => setActiveTab('fmp')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'fmp'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            FMP Market Data
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'fred' && <FREDIntegration />}
        {activeTab === 'fmp' && <FMPIntegration />}
      </div>
    </div>
  );
};

export default APIDashboard; 