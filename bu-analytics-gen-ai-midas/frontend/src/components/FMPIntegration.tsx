import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, Search, DollarSign, BarChart3, Info, Calendar, Building, Globe } from 'lucide-react';

interface FMPQuote {
  symbol: string;
  name: string;
  price: number;
  changesPercentage: number;
  change: number;
  dayLow: number;
  dayHigh: number;
  yearHigh: number;
  yearLow: number;
  marketCap: number;
  priceAvg50: number;
  priceAvg200: number;
  volume: number;
  avgVolume: number;
  exchange: string;
  open: number;
  previousClose: number;
  eps: number;
  pe: number;
  earningsAnnouncement: string;
  sharesOutstanding: number;
  timestamp: number;
}

interface FMPHistoricalData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adjClose: number;
  volume: number;
  unadjustedVolume: number;
  change: number;
  changePercent: number;
  vwap: number;
  label: string;
  changeOverTime: number;
}

interface FMPCompanyProfile {
  symbol: string;
  price: number;
  beta: number;
  volAvg: number;
  mktCap: number;
  lastDiv: number;
  range: string;
  changes: number;
  companyName: string;
  currency: string;
  cik: string;
  isin: string;
  cusip: string;
  exchange: string;
  exchangeShortName: string;
  industry: string;
  website: string;
  description: string;
  ceo: string;
  sector: string;
  country: string;
  fullTimeEmployees: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  dcfDiff: number;
  dcf: number;
  image: string;
  ipoDate: string;
  defaultImage: boolean;
  isEtf: boolean;
  isActivelyTrading: boolean;
  isAdr: boolean;
  isFund: boolean;
}

const FMPIntegration: React.FC = () => {
  const API_KEY = 'ynsIKE9Jo8eUCAH7wk2HmmXmkog9M6kb';
  const BASE_URL = 'https://financialmodelingprep.com/api/v3';

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('AAPL');
  const [quote, setQuote] = useState<FMPQuote | null>(null);
  const [historicalData, setHistoricalData] = useState<FMPHistoricalData[]>([]);
  const [companyProfile, setCompanyProfile] = useState<FMPCompanyProfile | null>(null);
  const [activeTab, setActiveTab] = useState<'quote' | 'chart' | 'profile'>('quote');

  // Popular stocks for quick access
  const popularStocks = [
    { symbol: 'AAPL', name: 'Apple Inc.' },
    { symbol: 'MSFT', name: 'Microsoft Corp.' },
    { symbol: 'GOOGL', name: 'Alphabet Inc.' },
    { symbol: 'AMZN', name: 'Amazon.com Inc.' },
    { symbol: 'TSLA', name: 'Tesla Inc.' },
    { symbol: 'NVDA', name: 'NVIDIA Corp.' },
    { symbol: 'META', name: 'Meta Platforms' },
    { symbol: 'JPM', name: 'JPMorgan Chase' }
  ];

  useEffect(() => {
    if (searchQuery) {
      fetchStockData(searchQuery);
    }
  }, [searchQuery]);

  const fetchStockData = async (symbol: string) => {
    setLoading(true);
    setError('');
    
    try {
      // Fetch real-time quote
      const quoteResponse = await fetch(
        `${BASE_URL}/quote/${symbol}?apikey=${API_KEY}`,
        {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
          }
        }
      );

      if (!quoteResponse.ok) {
        throw new Error(`FMP API error: ${quoteResponse.status} - ${quoteResponse.statusText}`);
      }

      const quoteData = await quoteResponse.json();
      
      if (quoteData.length === 0) {
        throw new Error(`Symbol "${symbol}" not found`);
      }

      setQuote(quoteData[0]);

      // Fetch historical data (last 30 days)
      const historicalResponse = await fetch(
        `${BASE_URL}/historical-price-full/${symbol}?apikey=${API_KEY}&timeseries=30`,
        {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
          }
        }
      );

      if (historicalResponse.ok) {
        const historicalResult = await historicalResponse.json();
        if (historicalResult.historical) {
          setHistoricalData(historicalResult.historical.reverse());
        }
      }

      // Fetch company profile
      const profileResponse = await fetch(
        `${BASE_URL}/profile/${symbol}?apikey=${API_KEY}`,
        {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
          }
        }
      );

      if (profileResponse.ok) {
        const profileData = await profileResponse.json();
        if (profileData.length > 0) {
          setCompanyProfile(profileData[0]);
        }
      }

    } catch (err) {
      setError(`Failed to fetch data: ${err instanceof Error ? err.message : 'Unknown error'}`);
      console.error('FMP API error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSymbolSelect = (symbol: string) => {
    setSearchQuery(symbol);
  };

  const handleSearch = () => {
    if (searchQuery.trim()) {
      fetchStockData(searchQuery.trim().toUpperCase());
    }
  };

  const formatCurrency = (value: number) => {
    if (value >= 1e12) {
      return `$${(value / 1e12).toFixed(2)}T`;
    } else if (value >= 1e9) {
      return `$${(value / 1e9).toFixed(2)}B`;
    } else if (value >= 1e6) {
      return `$${(value / 1e6).toFixed(2)}M`;
    } else if (value >= 1e3) {
      return `$${(value / 1e3).toFixed(2)}K`;
    } else {
      return `$${value.toFixed(2)}`;
    }
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1e9) {
      return `${(volume / 1e9).toFixed(2)}B`;
    } else if (volume >= 1e6) {
      return `${(volume / 1e6).toFixed(2)}M`;
    } else if (volume >= 1e3) {
      return `${(volume / 1e3).toFixed(2)}K`;
    } else {
      return volume.toLocaleString();
    }
  };

  const renderChart = () => {
    if (historicalData.length === 0) return null;

    const prices = historicalData.map(d => d.close);
    const maxPrice = Math.max(...prices);
    const minPrice = Math.min(...prices);
    const range = maxPrice - minPrice;

    return (
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg p-6 border border-green-200">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold text-gray-900">30-Day Price Chart</h4>
          <span className="text-sm text-gray-600">Daily Close Prices</span>
        </div>
        
        <div className="h-40 flex items-end space-x-1 mb-4">
          {historicalData.slice(-20).map((point, index) => {
            const height = range > 0 ? ((point.close - minPrice) / range) * 120 + 20 : 70;
            const isPositive = index > 0 ? point.close >= historicalData[historicalData.length - 20 + index - 1]?.close : true;
            
            return (
              <div
                key={index}
                className={`rounded-t hover:opacity-80 transition-colors cursor-pointer relative group flex-1 max-w-8 ${
                  isPositive ? 'bg-green-500' : 'bg-red-500'
                }`}
                style={{ height: `${height}px` }}
                title={`${point.date}: $${point.close.toFixed(2)}`}
              >
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                  {point.date}: ${point.close.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex justify-between text-sm text-gray-600">
          <span>{historicalData[Math.max(0, historicalData.length - 20)]?.date}</span>
          <span>{historicalData[historicalData.length - 1]?.date}</span>
        </div>
      </div>
    );
  };

  const renderQuoteTab = () => {
    if (!quote) return null;

    const isPositive = quote.change >= 0;

    return (
      <div className="space-y-6">
        {/* Main Price Display */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{quote.name}</h2>
              <p className="text-gray-600">{quote.symbol} • {quote.exchange}</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-gray-900">
                ${quote.price.toFixed(2)}
              </div>
              <div className={`flex items-center justify-end space-x-1 ${
                isPositive ? 'text-green-600' : 'text-red-600'
              }`}>
                {isPositive ? (
                  <TrendingUp className="h-4 w-4" />
                ) : (
                  <TrendingDown className="h-4 w-4" />
                )}
                <span className="font-medium">
                  {isPositive ? '+' : ''}{quote.change.toFixed(2)} ({isPositive ? '+' : ''}{quote.changesPercentage.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <DollarSign className="h-4 w-4 text-blue-600" />
                <span className="text-sm text-blue-600 font-medium">Day High</span>
              </div>
              <div className="text-lg font-bold text-gray-900">${quote.dayHigh.toFixed(2)}</div>
            </div>
            
            <div className="bg-red-50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <DollarSign className="h-4 w-4 text-red-600" />
                <span className="text-sm text-red-600 font-medium">Day Low</span>
              </div>
              <div className="text-lg font-bold text-gray-900">${quote.dayLow.toFixed(2)}</div>
            </div>
            
            <div className="bg-green-50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="text-sm text-green-600 font-medium">52W High</span>
              </div>
              <div className="text-lg font-bold text-gray-900">${quote.yearHigh.toFixed(2)}</div>
            </div>
            
            <div className="bg-orange-50 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingDown className="h-4 w-4 text-orange-600" />
                <span className="text-sm text-orange-600 font-medium">52W Low</span>
              </div>
              <div className="text-lg font-bold text-gray-900">${quote.yearLow.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* Market Data */}
        <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg p-6 border border-purple-200">
          <h4 className="font-semibold text-gray-900 mb-4">Market Information</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-gray-600">Market Cap</div>
              <div className="font-semibold text-gray-900">{formatCurrency(quote.marketCap)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Volume</div>
              <div className="font-semibold text-gray-900">{formatVolume(quote.volume)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Avg Volume</div>
              <div className="font-semibold text-gray-900">{formatVolume(quote.avgVolume)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">P/E Ratio</div>
              <div className="font-semibold text-gray-900">{quote.pe ? quote.pe.toFixed(2) : 'N/A'}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">EPS</div>
              <div className="font-semibold text-gray-900">${quote.eps ? quote.eps.toFixed(2) : 'N/A'}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Previous Close</div>
              <div className="font-semibold text-gray-900">${quote.previousClose ? quote.previousClose.toFixed(2) : 'N/A'}</div>
            </div>
          </div>
        </div>

        {/* Moving Averages */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">50-Day Average</div>
            <div className="font-semibold text-gray-900">${quote.priceAvg50.toFixed(2)}</div>
            <div className={`text-xs ${quote.price > quote.priceAvg50 ? 'text-green-600' : 'text-red-600'}`}>
              {quote.price > quote.priceAvg50 ? 'Above' : 'Below'} 50-day MA
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-sm text-gray-600">200-Day Average</div>
            <div className="font-semibold text-gray-900">${quote.priceAvg200.toFixed(2)}</div>
            <div className={`text-xs ${quote.price > quote.priceAvg200 ? 'text-green-600' : 'text-red-600'}`}>
              {quote.price > quote.priceAvg200 ? 'Above' : 'Below'} 200-day MA
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderProfileTab = () => {
    if (!companyProfile) return null;

    return (
      <div className="space-y-6">
        {/* Company Overview */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-start space-x-4 mb-6">
            {companyProfile.image && (
              <img 
                src={companyProfile.image} 
                alt={companyProfile.companyName}
                className="w-16 h-16 rounded-lg object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            )}
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-900">{companyProfile.companyName}</h2>
              <p className="text-gray-600">{companyProfile.symbol} • {companyProfile.exchangeShortName}</p>
              <div className="flex items-center space-x-4 mt-2 text-sm text-gray-600">
                <span>{companyProfile.sector}</span>
                <span>•</span>
                <span>{companyProfile.industry}</span>
                <span>•</span>
                <span>{companyProfile.country}</span>
              </div>
            </div>
          </div>

          <p className="text-gray-700 leading-relaxed">{companyProfile.description}</p>
        </div>

        {/* Company Details */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-4">Company Information</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">CEO</span>
                <span className="font-medium text-gray-900">{companyProfile.ceo || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Employees</span>
                <span className="font-medium text-gray-900">{companyProfile.fullTimeEmployees ? parseInt(companyProfile.fullTimeEmployees).toLocaleString() : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Founded</span>
                <span className="font-medium text-gray-900">{companyProfile.ipoDate || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Website</span>
                <a 
                  href={companyProfile.website} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="font-medium text-blue-600 hover:text-blue-700"
                >
                  {companyProfile.website ? 'Visit Website' : 'N/A'}
                </a>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-4">Financial Metrics</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Market Cap</span>
                <span className="font-medium text-gray-900">{formatCurrency(companyProfile.mktCap)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Beta</span>
                <span className="font-medium text-gray-900">{companyProfile.beta ? companyProfile.beta.toFixed(2) : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Last Dividend</span>
                <span className="font-medium text-gray-900">${companyProfile.lastDiv ? companyProfile.lastDiv.toFixed(2) : '0.00'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">52W Range</span>
                <span className="font-medium text-gray-900">{companyProfile.range || 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">FMP API Integration</h1>
        <p className="text-gray-600">Real-time Financial Market Data</p>
      </div>

      {/* Search Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center space-x-4 mb-4">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Enter stock symbol (e.g., AAPL, MSFT, GOOGL)"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            <span>Search</span>
          </button>
        </div>

        {/* Popular Stocks Quick Access */}
        <div className="mb-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Popular Stocks:</h3>
          <div className="flex flex-wrap gap-2">
            {popularStocks.map((stock) => (
              <button
                key={stock.symbol}
                onClick={() => handleSymbolSelect(stock.symbol)}
                className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                  searchQuery === stock.symbol
                    ? 'bg-blue-100 border-blue-500 text-blue-700'
                    : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'
                }`}
              >
                {stock.name} ({stock.symbol})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <div className="text-red-600 font-medium">Error</div>
          </div>
          <div className="text-red-700 mt-1">{error}</div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-4" />
          <div className="text-gray-600">Fetching market data...</div>
        </div>
      )}

      {/* Tabs */}
      {quote && !loading && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="border-b border-gray-200">
            <nav className="flex space-x-8 px-6">
              {[
                { id: 'quote', label: 'Real-time Quote', icon: DollarSign },
                { id: 'chart', label: 'Price Chart', icon: BarChart3 },
                { id: 'profile', label: 'Company Profile', icon: Building }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center space-x-2 py-4 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'quote' && renderQuoteTab()}
            {activeTab === 'chart' && renderChart()}
            {activeTab === 'profile' && renderProfileTab()}
          </div>
        </div>
      )}

      {/* API Info */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="flex items-start space-x-2">
          <Info className="h-5 w-5 text-green-600 mt-0.5" />
          <div>
            <div className="font-medium text-green-900">FMP API Integration Active</div>
            <div className="text-sm text-green-700 mt-1">
              Connected to Financial Modeling Prep API. All market data is fetched in real-time.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FMPIntegration; 