import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, Download, BarChart3, Search, Calendar, Info, Filter, Globe } from 'lucide-react';

interface FREDDataPoint {
  date: string;
  value: string;
}

interface FREDSeriesInfo {
  id: string;
  title: string;
  units: string;
  frequency: string;
  seasonal_adjustment: string;
  last_updated: string;
  notes?: string;
}

interface FREDSearchResult {
  id: string;
  title: string;
  units: string;
  frequency: string;
  popularity: number;
  last_updated: string;
}

const FREDIntegration: React.FC = () => {
  // FRED API key
  const API_KEY = '300d60db63932abff3c62c2bdcda2166';
  const BASE_URL = 'https://api.stlouisfed.org/fred';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('GDP');
  const [searchResults, setSearchResults] = useState<FREDSearchResult[]>([]);
  const [selectedSeries, setSelectedSeries] = useState<string>('GDP');
  const [seriesInfo, setSeriesInfo] = useState<FREDSeriesInfo | null>(null);
  const [seriesData, setSeriesData] = useState<FREDDataPoint[]>([]);
  const [showSearchResults, setShowSearchResults] = useState(false);

  // Popular economic indicators for quick access
  const popularSeries = [
    { id: 'GDP', name: 'Gross Domestic Product', category: 'Growth' },
    { id: 'UNRATE', name: 'Unemployment Rate', category: 'Labor' },
    { id: 'FEDFUNDS', name: 'Federal Funds Rate', category: 'Monetary Policy' },
    { id: 'CPIAUCSL', name: 'Consumer Price Index', category: 'Inflation' },
    { id: 'PAYEMS', name: 'Total Nonfarm Payrolls', category: 'Labor' },
    { id: 'HOUST', name: 'Housing Starts', category: 'Housing' },
    { id: 'INDPRO', name: 'Industrial Production', category: 'Production' },
    { id: 'DSPIC96', name: 'Real Disposable Income', category: 'Income' }
  ];

  // Economic categories for filtering
  const categories = ['All', 'Growth', 'Labor', 'Inflation', 'Monetary Policy', 'Housing', 'Production', 'Income'];
  const [selectedCategory, setSelectedCategory] = useState('All');

  useEffect(() => {
    // Load default series on component mount
    if (selectedSeries) {
      fetchSeriesData(selectedSeries);
    }
  }, [selectedSeries]);

  // JSONP implementation to bypass CORS
  const fetchWithJSONP = (url: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const callbackName = `fredCallback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const script = document.createElement('script');
      const timeoutId = setTimeout(() => {
        cleanup();
        reject(new Error('Request timeout'));
      }, 10000);

      const cleanup = () => {
        if (script.parentNode) {
          script.parentNode.removeChild(script);
        }
        delete (window as any)[callbackName];
        clearTimeout(timeoutId);
      };

      (window as any)[callbackName] = (data: any) => {
        cleanup();
        resolve(data);
      };

      script.src = `${url}&callback=${callbackName}`;
      script.onerror = () => {
        cleanup();
        reject(new Error('Script loading failed'));
      };

      document.head.appendChild(script);
    });
  };

  // Fallback to mock data if API fails
  const getMockSeriesInfo = (seriesId: string): FREDSeriesInfo => {
    const mockInfoMap: Record<string, FREDSeriesInfo> = {
      'GDP': {
        id: 'GDP',
        title: 'Gross Domestic Product',
        units: 'Billions of Dollars',
        frequency: 'Quarterly',
        seasonal_adjustment: 'Seasonally Adjusted Annual Rate',
        last_updated: '2024-01-15 09:45:00-06'
      },
      'UNRATE': {
        id: 'UNRATE',
        title: 'Unemployment Rate',
        units: 'Percent',
        frequency: 'Monthly',
        seasonal_adjustment: 'Seasonally Adjusted',
        last_updated: '2024-01-12 07:30:00-06'
      },
      'FEDFUNDS': {
        id: 'FEDFUNDS',
        title: 'Federal Funds Effective Rate',
        units: 'Percent',
        frequency: 'Monthly',
        seasonal_adjustment: 'Not Seasonally Adjusted',
        last_updated: '2024-01-10 16:00:00-06'
      },
      'CPIAUCSL': {
        id: 'CPIAUCSL',
        title: 'Consumer Price Index for All Urban Consumers: All Items',
        units: 'Index 1982-1984=100',
        frequency: 'Monthly',
        seasonal_adjustment: 'Seasonally Adjusted',
        last_updated: '2024-01-11 08:30:00-06'
      }
    };
    return mockInfoMap[seriesId] || mockInfoMap['GDP'];
  };

  const getMockSeriesData = (seriesId: string): FREDDataPoint[] => {
    const baseValue = seriesId === 'GDP' ? 26000 : 
                     seriesId === 'UNRATE' ? 3.8 :
                     seriesId === 'FEDFUNDS' ? 5.25 :
                     seriesId === 'CPIAUCSL' ? 310 : 100;
    
    const volatility = seriesId === 'GDP' ? 0.02 : 
                      seriesId === 'UNRATE' ? 0.05 :
                      seriesId === 'FEDFUNDS' ? 0.03 :
                      0.01;

    const data: FREDDataPoint[] = [];
    let currentValue = baseValue;
    const startDate = new Date(2022, 0, 1);

    for (let i = 0; i < 20; i++) {
      const date = new Date(startDate);
      if (seriesId === 'GDP') {
        date.setMonth(date.getMonth() + i * 3); // Quarterly
      } else {
        date.setMonth(date.getMonth() + i); // Monthly
      }
      
      currentValue = currentValue * (1 + (Math.random() - 0.5) * volatility);
      
      data.push({
        date: date.toISOString().split('T')[0],
        value: currentValue.toFixed(seriesId === 'GDP' ? 1 : 2)
      });
    }

    return data;
  };

  const fetchSeriesData = async (seriesId: string) => {
    setLoading(true);
    setError('');
    
    try {
      // Try JSONP first, then fall back to regular fetch, then mock data
      let infoData, observationData;
      
      try {
        // Try JSONP first
        infoData = await fetchWithJSONP(
          `${BASE_URL}/series?series_id=${seriesId}&api_key=${API_KEY}&file_type=json`
        );
        
        observationData = await fetchWithJSONP(
          `${BASE_URL}/series/observations?series_id=${seriesId}&api_key=${API_KEY}&file_type=json&limit=100&sort_order=desc`
        );
      } catch (jsonpError) {
        console.log('JSONP failed, trying regular fetch...', jsonpError);
        
        // Try regular fetch with mode: 'cors'
        try {
          const infoResponse = await fetch(
            `${BASE_URL}/series?series_id=${seriesId}&api_key=${API_KEY}&file_type=json`,
            { 
              method: 'GET',
              mode: 'cors',
              headers: {
                'Accept': 'application/json',
              }
            }
          );
          
          const dataResponse = await fetch(
            `${BASE_URL}/series/observations?series_id=${seriesId}&api_key=${API_KEY}&file_type=json&limit=100&sort_order=desc`,
            { 
              method: 'GET',
              mode: 'cors',
              headers: {
                'Accept': 'application/json',
              }
            }
          );

          if (infoResponse.ok && dataResponse.ok) {
            infoData = await infoResponse.json();
            observationData = await dataResponse.json();
          } else {
            throw new Error(`HTTP Error: ${infoResponse.status || dataResponse.status}`);
          }
        } catch (fetchError) {
          console.log('Regular fetch failed, using mock data...', fetchError);
          // Use mock data as fallback
          setSeriesInfo(getMockSeriesInfo(seriesId));
          setSeriesData(getMockSeriesData(seriesId));
          setError('Using demo data. FRED API may be experiencing issues or CORS restrictions.');
          setLoading(false);
          return;
        }
      }
      
      // Check for API errors
      if (infoData.error_code) {
        throw new Error(infoData.error_message || 'FRED API Error');
      }
      
      if (!infoData.seriess || infoData.seriess.length === 0) {
        throw new Error(`Series ${seriesId} not found`);
      }
      
      setSeriesInfo(infoData.seriess[0]);

      if (observationData.error_code) {
        throw new Error(observationData.error_message || 'FRED API Error');
      }
      
      if (observationData.observations) {
        // Filter out missing values and reverse to get chronological order
        const validData = observationData.observations
          .filter((obs: any) => obs.value !== '.')
          .reverse();
        setSeriesData(validData);
      } else {
        setSeriesData([]);
      }
      
      // Clear any previous errors if successful
      setError('');
      
    } catch (err) {
      console.error('FRED API Error:', err);
      
      // Use mock data as fallback
      setSeriesInfo(getMockSeriesInfo(seriesId));
      setSeriesData(getMockSeriesData(seriesId));
      setError('Using demo data. FRED API may be experiencing issues or CORS restrictions.');
    } finally {
      setLoading(false);
    }
  };

  const searchSeries = async (query: string) => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError('');
    
    try {
      let data;
      
      try {
        // Try JSONP first
        data = await fetchWithJSONP(
          `${BASE_URL}/series/search?search_text=${encodeURIComponent(query)}&api_key=${API_KEY}&file_type=json&limit=10`
        );
      } catch (jsonpError) {
        // Try regular fetch
        const response = await fetch(
          `${BASE_URL}/series/search?search_text=${encodeURIComponent(query)}&api_key=${API_KEY}&file_type=json&limit=10`,
          { 
            method: 'GET',
            mode: 'cors',
            headers: {
              'Accept': 'application/json',
            }
          }
        );
        
        if (!response.ok) {
          throw new Error(`Search failed: ${response.status}`);
        }
        
        data = await response.json();
      }
      
      if (data.error_code) {
        throw new Error(data.error_message || 'FRED API Search Error');
      }
      
      if (data.seriess) {
        setSearchResults(data.seriess);
        setShowSearchResults(true);
      } else {
        setSearchResults([]);
        setShowSearchResults(false);
      }
      
    } catch (err) {
      console.error('FRED Search Error:', err);
      
      // Fallback to popular series that match the query
      const mockResults = popularSeries
        .filter(series => 
          series.name.toLowerCase().includes(query.toLowerCase()) ||
          series.id.toLowerCase().includes(query.toLowerCase())
        )
        .map(series => ({
          id: series.id,
          title: series.name,
          units: series.id === 'GDP' ? 'Billions of Dollars' : 'Percent',
          frequency: series.id === 'GDP' ? 'Quarterly' : 'Monthly',
          popularity: 100,
          last_updated: '2024-01-15 09:45:00-06'
        }));
      
      setSearchResults(mockResults);
      setShowSearchResults(true);
      setError('Search using demo data. FRED API may be experiencing issues.');
    } finally {
      setLoading(false);
    }
  };

  const handleSeriesSelect = (seriesId: string) => {
    setSelectedSeries(seriesId);
    setShowSearchResults(false);
    setSearchQuery(seriesId);
  };

  const handleSearch = () => {
    searchSeries(searchQuery);
  };

  const getLatestValue = () => {
    if (seriesData.length === 0) return null;
    const latest = seriesData[seriesData.length - 1];
    return parseFloat(latest.value);
  };

  const getPreviousValue = () => {
    if (seriesData.length < 2) return null;
    const previous = seriesData[seriesData.length - 2];
    return parseFloat(previous.value);
  };

  const getChange = () => {
    const latest = getLatestValue();
    const previous = getPreviousValue();
    if (latest === null || previous === null) return null;
    return latest - previous;
  };

  const getChangePercent = () => {
    const latest = getLatestValue();
    const previous = getPreviousValue();
    const change = getChange();
    if (latest === null || previous === null || change === null) return null;
    return (change / previous) * 100;
  };

  const filteredSeries = selectedCategory === 'All' 
    ? popularSeries 
    : popularSeries.filter(series => series.category === selectedCategory);

  const renderChart = () => {
    if (!seriesData.length) return null;

    const maxValue = Math.max(...seriesData.map(d => parseFloat(d.value)));
    const minValue = Math.min(...seriesData.map(d => parseFloat(d.value)));
    const range = maxValue - minValue;

    return (
      <div className="space-y-4">
        <div className="h-80 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
          <div className="h-full relative">
            <svg width="100%" height="100%" className="absolute inset-0">
              <defs>
                <linearGradient id="fredChartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.1" />
                </linearGradient>
              </defs>
              
              {/* Grid lines */}
              {[0, 25, 50, 75, 100].map(y => (
                <line
                  key={y}
                  x1="0%"
                  y1={`${y}%`}
                  x2="100%"
                  y2={`${y}%`}
                  stroke="#E5E7EB"
                  strokeWidth="0.5"
                />
              ))}
              
              {/* Chart line */}
              <polyline
                fill="none"
                stroke="#3B82F6"
                strokeWidth="3"
                points={seriesData.map((point, index) => {
                  const x = (index / (seriesData.length - 1)) * 100;
                  const y = range > 0 ? 100 - ((parseFloat(point.value) - minValue) / range) * 85 : 50;
                  return `${x}%,${y}%`;
                }).join(' ')}
              />
              
              {/* Chart area */}
              <polygon
                fill="url(#fredChartGradient)"
                points={`0%,100% ${seriesData.map((point, index) => {
                  const x = (index / (seriesData.length - 1)) * 100;
                  const y = range > 0 ? 100 - ((parseFloat(point.value) - minValue) / range) * 85 : 50;
                  return `${x}%,${y}%`;
                }).join(' ')} 100%,100%`}
              />
              
              {/* Data points */}
              {seriesData.slice(-20).map((point, index) => {
                const x = ((seriesData.length - 20 + index) / (seriesData.length - 1)) * 100;
                const y = range > 0 ? 100 - ((parseFloat(point.value) - minValue) / range) * 85 : 50;
                return (
                  <circle
                    key={index}
                    cx={`${x}%`}
                    cy={`${y}%`}
                    r="4"
                    fill="#3B82F6"
                    className="hover:r-6 transition-all duration-200"
                  >
                    <title>{`${point.date}: ${parseFloat(point.value).toLocaleString()}`}</title>
                  </circle>
                );
              })}
            </svg>
          </div>
        </div>
        
        <div className="flex justify-between text-sm text-gray-500">
          <span>{seriesData[0]?.date}</span>
          <span>{seriesData[seriesData.length - 1]?.date}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">FRED Economic Data</h1>
          <p className="text-gray-600 mt-2">
            Federal Reserve Economic Data - Real-time economic indicators
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-2 text-green-600 bg-green-50 px-3 py-2 rounded-lg">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium">Live Data</span>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-4 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Search Bar */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center space-x-4 mb-4">
              <div className="flex-1">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search for economic data (e.g., inflation, employment, GDP)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <button
                onClick={handleSearch}
                disabled={loading}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
              >
                {loading ? <RefreshCw className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
                <span>Search</span>
              </button>
            </div>

            {/* Search Results */}
            {showSearchResults && searchResults.length > 0 && (
              <div className="space-y-2">
                <h3 className="font-medium text-gray-900">Search Results</h3>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {searchResults.map((result) => (
                    <button
                      key={result.id}
                      onClick={() => handleSeriesSelect(result.id)}
                      className="w-full text-left p-3 bg-gray-50 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      <div className="font-medium text-gray-900">{result.title}</div>
                      <div className="text-sm text-gray-500">
                        ID: {result.id} • {result.units} • {result.frequency}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Current Series Data */}
          {seriesInfo && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">{seriesInfo.title}</h2>
                  <div className="flex items-center space-x-4 text-sm text-gray-500">
                    <span>ID: {seriesInfo.id}</span>
                    <span>•</span>
                    <span>{seriesInfo.units}</span>
                    <span>•</span>
                    <span>{seriesInfo.frequency}</span>
                  </div>
                </div>
                {seriesData.length > 0 && (
                  <div className="text-right">
                    <div className="text-3xl font-bold text-gray-900">
                      {getLatestValue()?.toLocaleString() ?? 'N/A'}
                    </div>
                    <div className="text-sm text-gray-500 mb-2">
                      Latest ({seriesData[seriesData.length - 1]?.date})
                    </div>
                    {/* Change Indicator */}
                    {getChange() !== null && (
                      <div className="flex items-center justify-end space-x-1">
                        {getChange()! >= 0 ? (
                          <TrendingUp className="h-4 w-4 text-green-500" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-red-500" />
                        )}
                        <span className={`text-sm font-medium ${
                          getChange()! >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {getChange()! >= 0 ? '+' : ''}{getChange()!.toFixed(2)} ({getChange()! >= 0 ? '+' : ''}{getChangePercent()!.toFixed(2)}%)
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {loading ? (
                <div className="flex items-center justify-center h-80">
                  <div className="text-center">
                    <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Loading economic data...</p>
                  </div>
                </div>
              ) : seriesData.length > 0 ? (
                renderChart()
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p>No data available for this series</p>
                </div>
              )}

              {error && (
                <div className="flex items-center space-x-2 text-amber-600 bg-amber-50 p-4 rounded-lg mt-4">
                  <Info className="h-5 w-5" />
                  <span className="text-sm">{error}</span>
                </div>
              )}
            </div>
          )}

          {/* Data Table */}
          {seriesData.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Data Points</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Change</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {seriesData.slice(-10).reverse().map((point, index) => {
                      const currentValue = parseFloat(point.value);
                      const nextIndex = seriesData.length - 1 - index;
                      const nextValue = nextIndex < seriesData.length - 1 ? parseFloat(seriesData[nextIndex + 1].value) : null;
                      const change = nextValue ? currentValue - nextValue : null;
                      
                      return (
                        <tr key={point.date} className={index === 0 ? 'bg-blue-50' : ''}>
                          <td className="px-6 py-4 text-sm text-gray-900">{point.date}</td>
                          <td className="px-6 py-4 text-sm text-gray-900 text-right font-medium">
                            {currentValue.toLocaleString()}
                          </td>
                          <td className="px-6 py-4 text-sm text-right">
                            {change !== null ? (
                              <span className={`font-medium ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {change >= 0 ? '+' : ''}{change.toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Category Filter */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Categories</h3>
            <div className="space-y-2">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selectedCategory === category
                      ? 'bg-blue-100 text-blue-900 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>

          {/* Popular Series */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Popular Indicators</h3>
            <div className="space-y-2">
              {filteredSeries.map((series) => (
                <button
                  key={series.id}
                  onClick={() => handleSeriesSelect(series.id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    selectedSeries === series.id
                      ? 'bg-blue-100 border border-blue-200 text-blue-900'
                      : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <div className="font-medium text-sm">{series.name}</div>
                  <div className="text-xs text-gray-500">{series.id} • {series.category}</div>
                </button>
              ))}
            </div>
          </div>

          {/* API Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <Globe className="h-5 w-5 text-blue-600" />
              <span className="font-medium text-blue-900">About FRED</span>
            </div>
            <p className="text-sm text-blue-800">
              Federal Reserve Economic Data provides access to 820,000+ economic data series 
              from national, international, public, and private sources.
            </p>
            {error && (
              <p className="text-xs text-amber-700 mt-2">
                Note: Displaying demo data due to CORS restrictions. For live data, a backend proxy is recommended.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FREDIntegration; 