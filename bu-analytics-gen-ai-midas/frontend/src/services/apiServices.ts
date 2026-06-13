import { DatabaseConnection } from '../contexts/DatabaseContext';
import { FastAPIService } from './fastApiService';

export interface APIDataPoint {
  date: string;
  value: number;
  label?: string;
}

export interface APIDataSeries {
  id: string;
  title: string;
  units: string;
  frequency: string;
  data: APIDataPoint[];
  lastUpdated: string;
  source: string;
}

export interface FREDSeries {
  id: string;
  title: string;
  units: string;
  frequency: string;
  seasonal_adjustment: string;
  last_updated: string;
  popularity: number;
  group_popularity: number;
}

export interface FMPData {
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
  timestamp: number;
}

export interface MoonshotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface MoonshotResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: {
      role: string;
      content: string;
    };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

class FREDAPIService {
  private baseUrl = 'https://api.stlouisfed.org/fred';
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private withCORSProxy(url: string) {
    if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV !== 'production') {
      return `https://corsproxy.io/?${url}`;
    }
    return url;
  }

  async searchSeries(searchText: string, limit: number = 10): Promise<FREDSeries[]> {
    try {
      const url = `${this.baseUrl}/series/search?search_text=${encodeURIComponent(searchText)}&api_key=${this.apiKey}&file_type=json&limit=${limit}`;
      const response = await fetch(this.withCORSProxy(url));
      
      if (!response.ok) {
        throw new Error(`FRED API error: ${response.status}`);
      }

      const data = await response.json();
      return data.seriess || [];
    } catch (error) {
      console.error('FRED API search error:', error);
      throw error;
    }
  }

  async getSeriesData(seriesId: string, startDate?: string, endDate?: string): Promise<APIDataSeries> {
    try {
      let url = `${this.baseUrl}/series/observations?series_id=${seriesId}&api_key=${this.apiKey}&file_type=json`;
      
      if (startDate) {
        url += `&observation_start=${startDate}`;
      }
      if (endDate) {
        url += `&observation_end=${endDate}`;
      }

      const response = await fetch(this.withCORSProxy(url));
      
      if (!response.ok) {
        throw new Error(`FRED API error: ${response.status}`);
      }

      const data = await response.json();

      return {
        id: seriesId,
        title: seriesId,
        units: 'Units',
        frequency: 'Monthly',
        data: data.observations?.map((obs: any) => ({
          date: obs.date,
          value: parseFloat(obs.value) || 0,
          label: obs.date
        })) || [],
        lastUpdated: new Date().toISOString(),
        source: 'FRED'
      };
    } catch (error) {
      console.error('FRED API data error:', error);
      throw error;
    }
  }
}

class FMPAPIService {
  private baseUrl = 'https://financialmodelingprep.com/api/v3';
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private withCORSProxy(url: string) {
    if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV !== 'production') {
      return `https://corsproxy.io/?${url}`;
    }
    return url;
  }

  async getQuote(symbol: string): Promise<FMPData> {
    try {
      const url = `${this.baseUrl}/quote/${symbol}?apikey=${this.apiKey}`;
      const response = await fetch(this.withCORSProxy(url));

      if (!response.ok) {
        throw new Error(`FMP API error: ${response.status}`);
      }

      const data = await response.json();
      return data[0];
    } catch (error) {
      console.error('FMP API quote error:', error);
      throw error;
    }
  }

  async getHistoricalData(symbol: string, from?: string, to?: string): Promise<APIDataSeries> {
    try {
      let url = `${this.baseUrl}/historical-price-full/${symbol}?apikey=${this.apiKey}`;
      
      if (from) {
        url += `&from=${from}`;
      }
      if (to) {
        url += `&to=${to}`;
      }

      const response = await fetch(this.withCORSProxy(url));

      if (!response.ok) {
        throw new Error(`FMP API error: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        id: symbol,
        title: `${symbol} Historical Data`,
        units: 'USD',
        frequency: 'Daily',
        data: data.historical?.map((item: any) => ({
        date: item.date,
        value: item.close,
          label: item.date
        })) || [],
        lastUpdated: new Date().toISOString(),
        source: 'FMP'
      };
    } catch (error) {
      console.error('FMP API historical data error:', error);
      throw error;
    }
  }
}

class MoonshotAPIService {
  private baseUrl = 'https://api.moonshot.cn/v1';
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async getModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/models`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Moonshot API error: ${response.status}`);
      }

      const data = await response.json();
      return data.data?.map((model: any) => model.id) || [];
    } catch (error) {
      console.error('Moonshot API models error:', error);
      throw error;
    }
  }

  async sendMessage(messages: MoonshotMessage[], model: string = 'moonshot-v1-8k'): Promise<MoonshotResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model,
          messages: messages.map(msg => ({
            role: msg.role,
            content: msg.content
          }))
        })
      });

      if (!response.ok) {
        throw new Error(`Moonshot API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Moonshot API chat error:', error);
      throw error;
    }
  }
}

class GeminiAPIService {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async testConnection(): Promise<boolean> {
    try {
      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${this.apiKey}`);
      return response.ok;
    } catch (error) {
      console.error('Gemini API test error:', error);
      return false;
    }
  }

  async sendMessage(messages: any[], model: string = 'gemini-2.0-flash'): Promise<any> {
    try {
      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${this.apiKey}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          contents: messages.map(msg => ({
            role: msg.role,
            parts: [{ text: msg.content }]
          }))
        })
      });

      if (!response.ok) {
        throw new Error(`Gemini API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Gemini API error:', error);
      throw error;
    }
  }
}

export class APIIntegrationService {
  private fredService: FREDAPIService | null = null;
  private fmpService: FMPAPIService | null = null;
  private moonshotService: MoonshotAPIService | null = null;
  private geminiService: GeminiAPIService | null = null;
  private fastApiService: FastAPIService | null = null;

  constructor() {
    // Auto-initialize services with environment variables if available
    this.initializeFromEnvironment();
  }

  private initializeFromEnvironment() {
    console.log('🔧 Auto-initializing API services from environment variables...');
    
    // Initialize Gemini/Vertex AI if API key is available
    const geminiApiKey = import.meta.env.VITE_GEMINI_API_KEY || import.meta.env.VITE_GOOGLE_CLOUD_API_KEY;
    if (geminiApiKey && geminiApiKey !== 'your_google_cloud_api_key_here') {
      console.log('🚀 Auto-initializing Vertex AI with environment API key');
      this.initializeGemini(geminiApiKey);
    }

    // Initialize other services if their keys are available
    const fredApiKey = import.meta.env.VITE_FRED_API_KEY;
    if (fredApiKey && fredApiKey !== 'your_fred_api_key_here') {
      console.log('🚀 Auto-initializing FRED with environment API key');
      this.initializeFRED(fredApiKey);
    }

    const fmpApiKey = import.meta.env.VITE_FMP_API_KEY;
    if (fmpApiKey && fmpApiKey !== 'your_fmp_api_key_here') {
      console.log('🚀 Auto-initializing FMP with environment API key');
      this.initializeFMP(fmpApiKey);
    }

    const moonshotApiKey = import.meta.env.VITE_MOONSHOT_API_KEY;
    if (moonshotApiKey && moonshotApiKey !== 'your_moonshot_api_key_here') {
      console.log('🚀 Auto-initializing Moonshot with environment API key');
      this.initializeMoonshot(moonshotApiKey);
    }

    // Initialize FastAPI service
    this.initializeFastAPI();
  }

  // Check if Vertex AI is already initialized from environment
  isVertexAIReady(): boolean {
    return this.geminiService !== null;
  }

  // Get the current Gemini API key from environment
  getGeminiApiKey(): string | null {
    return import.meta.env.VITE_GEMINI_API_KEY || import.meta.env.VITE_GOOGLE_CLOUD_API_KEY || null;
  }

  initializeFRED(apiKey: string) {
    this.fredService = new FREDAPIService(apiKey);
  }

  initializeFMP(apiKey: string) {
    this.fmpService = new FMPAPIService(apiKey);
  }

  initializeMoonshot(apiKey: string) {
    this.moonshotService = new MoonshotAPIService(apiKey);
  }

  initializeGemini(apiKey: string) {
    console.log('🔧 Initializing Gemini Service with key:', apiKey ? `${apiKey.substring(0, 10)}...` : 'NOT SET');
    this.geminiService = new GeminiAPIService(apiKey);
    console.log('✅ Gemini Service initialized:', !!this.geminiService);
    
    // Test the connection
    if (this.geminiService) {
      this.geminiService.testConnection().then(success => {
        console.log('🧪 Gemini API connection test result:', success);
      });
    }
  }

  initializeFastAPI(baseUrl?: string) {
    // Always use environment variable if baseUrl is not explicitly provided.
    // Normalize to avoid accidental '/api/v1/api/v1'.
    const envBaseUrlRaw = (import.meta.env.VITE_BASE_URL || '').trim();
    const envBaseUrl = envBaseUrlRaw.replace(/\/+$/, '');
    const normalizedEnvBase = envBaseUrl
      ? (envBaseUrl.endsWith('/api/v1') ? envBaseUrl : `${envBaseUrl}/api/v1`)
      : '/api/v1';
    const finalBaseUrl = (baseUrl || normalizedEnvBase).replace(/\/+$/, '');
    console.log('🔧 Initializing FastAPI Service with base URL:', finalBaseUrl);
    console.log('🔧 VITE_BASE_URL from env:', envBaseUrlRaw || undefined);
    this.fastApiService = new FastAPIService(finalBaseUrl);
    console.log('✅ FastAPI Service initialized:', !!this.fastApiService);
    
    // Test the connection
    if (this.fastApiService) {
      this.fastApiService.healthCheck().then(success => {
        console.log('🧪 FastAPI backend health check result:', success);
      });
    }
  }

  getFREDService(): FREDAPIService | null {
    return this.fredService;
  }

  getFMPService(): FMPAPIService | null {
    return this.fmpService;
  }

  getMoonshotService(): MoonshotAPIService | null {
    return this.moonshotService;
  }

  getGeminiService(): GeminiAPIService | null {
    return this.geminiService;
  }

  getFastAPIService(): FastAPIService | null {
    return this.fastApiService;
  }

  async testGeminiConnection(): Promise<boolean> {
    try {
      console.log('🧪 Testing Gemini connection directly...');
      if (!this.geminiService) {
        console.error('❌ Gemini service not initialized');
        return false;
      }
      
      const result = await this.geminiService.testConnection();
      console.log('🧪 Direct Gemini test result:', result);
      return result;
    } catch (error) {
      console.error('❌ Direct Gemini test error:', error);
      return false;
    }
  }

  async testFastAPIConnection(): Promise<boolean> {
    try {
      console.log('🧪 Testing FastAPI connection directly...');
      if (!this.fastApiService) {
        console.error('❌ FastAPI service not initialized');
        return false;
      }
      
      const result = await this.fastApiService.healthCheck();
      console.log('🧪 Direct FastAPI test result:', result);
      return result;
    } catch (error) {
      console.error('❌ Direct FastAPI test error:', error);
      return false;
    }
  }

  async testConnection(connection: DatabaseConnection): Promise<boolean> {
    try {
      switch (connection.type) {
        case 'fred_api':
          if (!connection.config.apiKey) return false;
          const fredService = new FREDAPIService(connection.config.apiKey);
          const series = await fredService.searchSeries('GDP', 1);
          return series.length > 0;

        case 'fmp_api':
          if (!connection.config.apiKey) return false;
          const fmpService = new FMPAPIService(connection.config.apiKey);
          const quote = await fmpService.getQuote('AAPL');
          return !!quote.symbol;

        case 'moonshot_api':
          if (!connection.config.apiKey) return false;
          const moonshotService = new MoonshotAPIService(connection.config.apiKey);
          const models = await moonshotService.getModels();
          return models.length > 0;

        default:
          return false;
      }
    } catch (error) {
      console.error('API connection test failed:', error);
      return false;
    }
  }
}

export const apiIntegrationService = new APIIntegrationService();
