import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, Download, Calendar, DollarSign, Percent, BarChart3 } from 'lucide-react';
import { useDatabase } from '../contexts/DatabaseContext';
import { apiIntegrationService, APIDataSeries, FMPData } from '../services/apiServices';

interface APIDataDisplayProps {
  connectionId: string;
  type: 'fred' | 'fmp';
}

const APIDataDisplay: React.FC<APIDataDisplayProps> = ({ connectionId, type }) => {
  const { getConnectionById } = useDatabase();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [fredData, setFredData] = useState<APIDataSeries | null>(null);
  const [fmpData, setFmpData] = useState<FMPData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const connection = getConnectionById(connectionId);

  useEffect(() => {
    if (connection && connection.config.apiKey) {
      if (type === 'fred') {
        apiIntegrationService.initializeFRED(connection.config.apiKey);
        fetchFREDData('GDP'); // Default to GDP data
      } else if (type === 'fmp') {
        apiIntegrationService.initializeFMP(connection.config.apiKey);
        fetchFMPData('AAPL'); // Default to Apple stock
      }
    }
  }, [connection, type]);

  const fetchFREDData = async (seriesId: string) => {
    setLoading(true);
    setError('');
    
    try {
      const fredService = apiIntegrationService.getFREDService();
      if (!fredService) {
        throw new Error('FRED service not initialized');
      }

      const data = await fredService.getSeriesData(seriesId);
      setFredData(data);
    } catch (err) {
      setError('Failed to fetch FRED data. Please check your API key and try again.');
      console.error('FRED data fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFMPData = async (symbol: string) => {
    setLoading(true);
    setError('');
    
    try {
      const fmpService = apiIntegrationService.getFMPService();
      if (!fmpService) {
        throw new Error('FMP service not initialized');
      }

      const data = await fmpService.getQuote(symbol);
      setFmpData(data);
    } catch (err) {
      setError('Failed to fetch FMP data. Please check your API key and try again.');
      console.error('FMP data fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    if (!searchQuery.trim()) return;
    
    if (type === 'fred') {
      fetchFREDData(searchQuery.toUpperCase());
    } else if (type === 'fmp') {
      fetchFMPData(searchQuery.toUpperCase());
    }
  };

  const renderFREDData = () => {
    if (!fredData) return null;

    const latestValue = fredData.data[fredData.data.length - 1];
    const previousValue = fredData.data[fredData.data.length - 2];
    const change = latestValue && previousValue ? latestValue.value - previousValue.value : 0;
    const changePercent = previousValue ? (change / previousValue.value) * 100 : 0;

    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{fredData.title}</h3>
            <p className="text-sm text-gray-600">Source: {fredData.source}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">
              {latestValue ? latestValue.value.toLocaleString() : 'N/A'}
            </div>
            <div className="text-sm text-gray-600">{fredData.units}</div>
          </div>
        </div>

        {/* Change Indicator */}
        {latestValue && previousValue && (
          <div className="flex items-center space-x-2">
            {change >= 0 ? (
              <TrendingUp className="h-4 w-4 text-green-500" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-500" />
            )}
            <span className={`text-sm font-medium ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)} ({changePercent >= 0 ? '+' : ''}{changePercent.toFixed(2)}%)
            </span>
            <span className="text-sm text-gray-500">vs previous period</span>
          </div>
        )}

        {/* Chart Visualization */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-medium text-gray-900">Historical Data</h4>
            <span className="text-sm text-gray-600">{fredData.frequency}</span>
          </div>
          
          {/* Simple line chart representation */}
          <div className="h-32 flex items-end space-x-1">
            {fredData.data.slice(-20).map((point, index) => {
              const maxValue = Math.max(...fredData.data.slice(-20).map(p => p.value));
              const minValue = Math.min(...fredData.data.slice(-20).map(p => p.value));
              const height = ((point.value - minValue) / (maxValue - minValue)) * 100 + 10;
              
              return (
                <div
                  key={index}
                  className="bg-blue-500 rounded-t hover:bg-blue-600 transition-colors cursor-pointer relative group"
                  style={{ height: `${height}%`, width: '4px' }}
                  title={`${point.date}: ${point.value}`}
                >
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    {point.date}: {point.value.toLocaleString()}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Data Info */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">Frequency</div>
            <div className="font-semibold text-gray-900">{fredData.frequency}</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">Last Updated</div>
            <div className="font-semibold text-gray-900">
              {new Date(fredData.lastUpdated).toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderFMPData = () => {
    if (!fmpData) return null;

    const isPositiveChange = fmpData.change >= 0;

    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{fmpData.name}</h3>
            <p className="text-sm text-gray-600">{fmpData.symbol} • {fmpData.exchange}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">
              ${fmpData.price.toFixed(2)}
            </div>
            <div className={`text-sm font-medium ${isPositiveChange ? 'text-green-600' : 'text-red-600'}`}>
              {isPositiveChange ? '+' : ''}{fmpData.change.toFixed(2)} ({isPositiveChange ? '+' : ''}{fmpData.changesPercentage.toFixed(2)}%)
            </div>
          </div>
        </div>

        {/* Price Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <DollarSign className="h-4 w-4 text-blue-600" />
              <span className="text-sm text-blue-600 font-medium">Day High</span>
            </div>
            <div className="text-lg font-bold text-gray-900">${fmpData.dayHigh.toFixed(2)}</div>
          </div>
          
          <div className="bg-red-50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <DollarSign className="h-4 w-4 text-red-600" />
              <span className="text-sm text-red-600 font-medium">Day Low</span>
            </div>
            <div className="text-lg font-bold text-gray-900">${fmpData.dayLow.toFixed(2)}</div>
          </div>
          
          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <TrendingUp className="h-4 w-4 text-green-600" />
              <span className="text-sm text-green-600 font-medium">52W High</span>
            </div>
            <div className="text-lg font-bold text-gray-900">${fmpData.yearHigh.toFixed(2)}</div>
          </div>
          
          <div className="bg-orange-50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <TrendingDown className="h-4 w-4 text-orange-600" />
              <span className="text-sm text-orange-600 font-medium">52W Low</span>
            </div>
            <div className="text-lg font-bold text-gray-900">${fmpData.yearLow.toFixed(2)}</div>
          </div>
        </div>

        {/* Market Data */}
        <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg p-6">
          <h4 className="font-medium text-gray-900 mb-4">Market Information</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-600">Market Cap</div>
              <div className="font-semibold text-gray-900">
                ${(fmpData.marketCap / 1000000000).toFixed(2)}B
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Volume</div>
              <div className="font-semibold text-gray-900">
                {(fmpData.volume / 1000000).toFixed(2)}M
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Avg Volume</div>
              <div className="font-semibold text-gray-900">
                {(fmpData.avgVolume / 1000000).toFixed(2)}M
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Last Updated</div>
              <div className="font-semibold text-gray-900">
                {new Date(fmpData.timestamp).toLocaleString()}
              </div>
            </div>
          </div>
        </div>

        {/* Moving Averages */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">50-Day MA</div>
            <div className="font-semibold text-gray-900">${fmpData.priceAvg50.toFixed(2)}</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">200-Day MA</div>
            <div className="font-semibold text-gray-900">${fmpData.priceAvg200.toFixed(2)}</div>
          </div>
        </div>
      </div>
    );
  };

  if (!connection) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-500">Connection not found</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      {/* Search Header */}
      <div className="flex items-center space-x-4 mb-6">
        <div className="flex-1">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={type === 'fred' ? 'Enter FRED series ID (e.g., GDP, UNRATE)' : 'Enter stock symbol (e.g., AAPL, MSFT)'}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
        </div>
        <button
          onClick={handleSearch}
          disabled={loading || !searchQuery.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
          <span>{loading ? 'Loading...' : 'Fetch Data'}</span>
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-center space-x-2">
            <div className="text-red-600 font-medium">Error</div>
          </div>
          <div className="text-red-700 mt-1">{error}</div>
        </div>
      )}

      {/* Data Display */}
      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-4" />
          <div className="text-gray-600">Fetching {type.toUpperCase()} data...</div>
        </div>
      ) : (
        <>
          {type === 'fred' && fredData && renderFREDData()}
          {type === 'fmp' && fmpData && renderFMPData()}
          {!fredData && !fmpData && !error && (
            <div className="text-center py-12">
              <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <div className="text-gray-600">
                Enter a {type === 'fred' ? 'FRED series ID' : 'stock symbol'} to fetch data
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default APIDataDisplay; 