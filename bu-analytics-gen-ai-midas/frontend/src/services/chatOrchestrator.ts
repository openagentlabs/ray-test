import { apiIntegrationService, MoonshotMessage, MoonshotResponse } from './apiServices';

export interface UserPreferences {
  dataSource: 'dataset' | 'fred' | 'fmp';
  llmModel: 'moonshot' | 'gemini';
  activeDataset?: any; // Dataset object when dataSource is 'dataset'
  selectedGeminiModel?: string; // Specific Gemini model to use
}

export interface ChatAPIResponse {
  id: string;
  content: string;
  source: 'moonshot' | 'fred' | 'fmp' | 'gemini' | 'combined';
  timestamp: number;
  hasChart?: boolean;
  chartType?: 'bar' | 'line' | 'pie' | 'table';
  rawData?: any;
  apiCalls?: {
    moonshot?: boolean;
    fred?: boolean;
    fmp?: boolean;
    gemini?: boolean;
  };
}

interface QueryAnalysis {
  intent: 'economic_data' | 'market_data' | 'general_analysis' | 'mixed';
  keywords: string[];
  needsFRED: boolean;
  needsFMP: boolean;
  needsMoonshot: boolean;
  needsGemini: boolean;
  entities: {
    tickers?: string[];
    economicIndicators?: string[];
    dateRanges?: string[];
  };
}

export class ChatOrchestrator {
  private moonshotApiKey: string;
  private fredApiKey: string;
  private fmpApiKey: string;
  private geminiApiKey: string;

  constructor() {
    // Load API keys from environment variables (no hardcoded fallbacks)
    this.moonshotApiKey = import.meta.env.VITE_MOONSHOT_API_KEY || '';
    this.fredApiKey = import.meta.env.VITE_FRED_API_KEY || '';
    this.fmpApiKey = import.meta.env.VITE_FMP_API_KEY || '';
    this.geminiApiKey = import.meta.env.VITE_GEMINI_API_KEY || '';
    
    console.log('🔑 API Keys Debug:', {
      moonshot: this.moonshotApiKey ? `${this.moonshotApiKey.substring(0, 10)}...` : 'NOT SET',
      fred: this.fredApiKey ? `${this.fredApiKey.substring(0, 10)}...` : 'NOT SET',
      fmp: this.fmpApiKey ? `${this.fmpApiKey.substring(0, 10)}...` : 'NOT SET',
      gemini: this.geminiApiKey ? `${this.geminiApiKey.substring(0, 10)}...` : 'NOT SET',
      moonshotFromEnv: import.meta.env.VITE_MOONSHOT_API_KEY ? 'LOADED FROM ENV' : 'USING FALLBACK',
      fredFromEnv: import.meta.env.VITE_FRED_API_KEY ? 'LOADED FROM ENV' : 'USING FALLBACK',
      fmpFromEnv: import.meta.env.VITE_FMP_API_KEY ? 'LOADED FROM ENV' : 'USING FALLBACK',
      geminiFromEnv: import.meta.env.VITE_GEMINI_API_KEY ? 'LOADED FROM ENV' : 'USING FALLBACK',
      allEnvVars: Object.keys(import.meta.env).filter(key => key.startsWith('VITE_')),
      envKeys: Object.keys(import.meta.env).filter(key => key.includes('API_KEY'))
    });
    
    // Initialize API services
    this.initializeServices();
  }

  private initializeServices() {
    console.log('🔧 Initializing API Services...');
    apiIntegrationService.initializeMoonshot(this.moonshotApiKey);
    apiIntegrationService.initializeFRED(this.fredApiKey);
    apiIntegrationService.initializeFMP(this.fmpApiKey);
    apiIntegrationService.initializeGemini(this.geminiApiKey);
    
    // Check if services are available
    console.log('✅ Services Status:', {
      moonshot: !!apiIntegrationService.getMoonshotService(),
      fred: !!apiIntegrationService.getFREDService(),
      fmp: !!apiIntegrationService.getFMPService(),
      gemini: !!apiIntegrationService.getGeminiService()
    });
    
    // Test Gemini connection directly
    if (apiIntegrationService.getGeminiService()) {
      console.log('🧪 Testing Gemini connection during initialization...');
      apiIntegrationService.testGeminiConnection().then(success => {
        console.log('🧪 Gemini connection test result:', success);
        
        // If connection test passes, try a simple request
        if (success) {
          console.log('🧪 Testing Gemini simple request...');
          const geminiService = apiIntegrationService.getGeminiService();
          if (geminiService) {
            geminiService.testSimpleRequest().then(simpleSuccess => {
              console.log('🧪 Gemini simple request test result:', simpleSuccess);
            });
          }
        }
      });
    }
    
    // Test all API keys after a short delay
    setTimeout(() => {
      this.testAllAPIKeys().then(results => {
        console.log('🧪 Final API key test results:', results);
      });
    }, 2000);
  }

  async processUserQuery(
    query: string, 
    conversationHistory: MoonshotMessage[] = [], 
    preferences?: UserPreferences
  ): Promise<ChatAPIResponse> {
    try {
      // Step 1: Analyze the query and apply user preferences
      const analysis = this.analyzeQuery(query);
      
      // Apply user preferences while preserving query analysis
      if (preferences) {
        // Only override data source if user explicitly selected one
        if (preferences.dataSource === 'fred') {
          analysis.needsFRED = true;
          analysis.needsFMP = false; // Don't fetch FMP if user selected FRED
        } else if (preferences.dataSource === 'fmp') {
          analysis.needsFMP = true;
          analysis.needsFRED = false; // Don't fetch FRED if user selected FMP
        }
        // If dataset is selected, don't fetch external APIs
        
        // Set LLM preferences
        analysis.needsGemini = preferences.llmModel === 'gemini';
        analysis.needsMoonshot = preferences.llmModel === 'moonshot';
      }
      
      // Step 2: Gather data from relevant APIs based on preferences
      const apiData = await this.gatherAPIData(analysis, query, preferences);
      
      // Step 3: Use selected LLM to synthesize the response
      const synthesizedResponse = await this.synthesizeResponse(query, apiData, conversationHistory, preferences?.llmModel || 'moonshot', preferences?.selectedGeminiModel);
      
      return {
        id: `chat-${Date.now()}`,
        content: synthesizedResponse.content,
        source: this.determineSourceFromPreferences(preferences) || this.determineSource(analysis),
        timestamp: Date.now(),
        hasChart: this.shouldGenerateChart(analysis, apiData),
        chartType: this.determineChartType(analysis, apiData),
        rawData: apiData,
        apiCalls: {
          moonshot: analysis.needsMoonshot,
          fred: analysis.needsFRED,
          fmp: analysis.needsFMP,
          gemini: analysis.needsGemini
        }
      };
    } catch (error) {
      console.error('Chat orchestrator error:', error);
      return this.createFallbackResponse(query);
    }
  }

  private analyzeQuery(query: string): QueryAnalysis {
    const lowerQuery = query.toLowerCase();
    
    // Economic data keywords
    const economicKeywords = ['gdp', 'unemployment', 'inflation', 'interest rate', 'fed funds', 'economic', 'economy', 'monetary policy', 'federal reserve', 'employment', 'housing', 'retail', 'industrial'];
    const marketKeywords = ['stock', 'price', 'market', 'trading', 'nasdaq', 'dow', 'sp500', 'earnings', 'revenue', 'financial ratios', 'company', 'corporation'];
    const generalKeywords = ['analyze', 'explain', 'help', 'what is', 'how does', 'summary', 'report', 'trend', 'performance'];
    
    // Extract potential stock tickers (improved pattern)
    const tickerPattern = /\b[A-Z]{1,5}\b/g;
    const potentialTickers = query.match(tickerPattern) || [];
    
    // Extract economic indicators with better matching
    const economicIndicators = economicKeywords.filter(keyword => 
      lowerQuery.includes(keyword)
    );
    
    // Extract company names and map to tickers
    const companyTickers = this.extractCompanyTickers(lowerQuery);
    const allTickers = [...potentialTickers, ...companyTickers];
    
    // Determine intent
    let intent: QueryAnalysis['intent'] = 'general_analysis';
    const hasEconomicData = economicKeywords.some(keyword => lowerQuery.includes(keyword));
    const hasMarketData = marketKeywords.some(keyword => lowerQuery.includes(keyword)) || allTickers.length > 0;
    
    if (hasEconomicData && hasMarketData) {
      intent = 'mixed';
    } else if (hasEconomicData) {
      intent = 'economic_data';
    } else if (hasMarketData) {
      intent = 'market_data';
    }
    
    return {
      intent,
      keywords: [...economicKeywords, ...marketKeywords, ...generalKeywords].filter(k => 
        lowerQuery.includes(k)
      ),
      needsFRED: hasEconomicData || intent === 'mixed',
      needsFMP: hasMarketData || intent === 'mixed' || allTickers.length > 0,
      needsMoonshot: true, // Always use Moonshot for synthesis
      needsGemini: false, // Will be determined by user preference
      entities: {
        tickers: allTickers.filter(ticker => 
          ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA', 'NFLX', 'DIS', 'KO', 'MCD', 'WMT', 'HD', 'JPM', 'BAC', 'WFC'].includes(ticker)
        ),
        economicIndicators,
        dateRanges: this.extractDateRanges(query)
      }
    };
  }

  private extractCompanyTickers(query: string): string[] {
    const tickers: string[] = [];
    
    // Company name to ticker mapping
    const companyMap: { [key: string]: string } = {
      'apple': 'AAPL',
      'google': 'GOOGL',
      'alphabet': 'GOOGL',
      'microsoft': 'MSFT',
      'tesla': 'TSLA',
      'amazon': 'AMZN',
      'meta': 'META',
      'facebook': 'META',
      'nvidia': 'NVDA',
      'netflix': 'NFLX',
      'disney': 'DIS',
      'coca cola': 'KO',
      'coke': 'KO',
      'mcdonalds': 'MCD',
      'walmart': 'WMT',
      'home depot': 'HD',
      'jpmorgan': 'JPM',
      'jp morgan': 'JPM',
      'bank of america': 'BAC',
      'wells fargo': 'WFC'
    };
    
    for (const [company, ticker] of Object.entries(companyMap)) {
      if (query.includes(company)) {
        tickers.push(ticker);
      }
    }
    
    return tickers;
  }

  private extractDateRanges(query: string): string[] {
    const datePatterns = [
      /\b(\d{4})\b/g, // Years
      /\b(q[1-4]|quarter [1-4])\b/gi, // Quarters
      /\b(last \w+|past \w+|recent)\b/gi // Relative dates
    ];
    
    const dates: string[] = [];
    datePatterns.forEach(pattern => {
      const matches = query.match(pattern);
      if (matches) dates.push(...matches);
    });
    
    return dates;
  }

  private async gatherAPIData(analysis: QueryAnalysis, query: string, preferences?: UserPreferences): Promise<any> {
    const data: any = {};
    
    try {
      console.log('🔍 Gathering API data for query:', query);
      console.log('📊 Analysis:', analysis);
      console.log('⚙️ Preferences:', preferences);
      
      // Handle dataset data if preferences specify dataset as source
      if (preferences?.dataSource === 'dataset' && preferences.activeDataset) {
        console.log('📁 Loading dataset data');
        data.dataset = {
          name: preferences.activeDataset.name,
          description: preferences.activeDataset.description,
          records: preferences.activeDataset.records,
          columns: preferences.activeDataset.columns,
          data: preferences.activeDataset.data, // Use ALL data instead of just first 50 rows
          totalRecords: preferences.activeDataset.data.length
        };
        console.log(`✅ Loaded complete dataset: ${data.dataset.totalRecords} rows, ${data.dataset.columns.length} columns`);
        console.log(`🔍 Data sample (first 5 rows):`, data.dataset.data.slice(0, 5));
        console.log(`📊 Dataset will be analyzed with: ${data.dataset.data.length <= 100 ? 'all rows' : data.dataset.data.length <= 1000 ? 'sample + summary' : 'comprehensive summary'}`);
        
        // Verify we have the complete dataset
        if (data.dataset.data.length === data.dataset.totalRecords) {
          console.log(`✅ Full dataset confirmed: ${data.dataset.data.length} rows loaded`);
        } else {
          console.warn(`⚠️ Dataset mismatch: loaded ${data.dataset.data.length} but expected ${data.dataset.totalRecords}`);
        }
      }
      
      // Gather FRED data if needed
      if (analysis.needsFRED || preferences?.dataSource === 'fred') {
        console.log('📈 Gathering FRED economic data');
        const fredService = apiIntegrationService.getFREDService();
        if (fredService) {
          const indicator = this.extractFREDIndicator(query, analysis);
          const seriesId = this.mapIndicatorToFREDSeries(indicator);
          console.log(`🔍 Using FRED series: ${seriesId} for indicator: ${indicator}`);
          
          try {
          data.fred = await fredService.getSeriesData(seriesId);
            console.log('✅ FRED data loaded successfully:', data.fred.title);
          } catch (error) {
            console.error('❌ FRED API error:', error);
            // Try fallback to GDP
            try {
              data.fred = await fredService.getSeriesData('GDP');
              console.log('🔄 Using GDP as FRED fallback');
            } catch (fallbackError) {
              console.error('❌ FRED fallback also failed:', fallbackError);
            }
          }
        }
      }
      
      // Gather FMP data if needed
      if (analysis.needsFMP || preferences?.dataSource === 'fmp') {
        console.log('📊 Gathering FMP market data');
        const fmpService = apiIntegrationService.getFMPService();
        if (fmpService) {
          const ticker = this.extractFMPTicker(query, analysis);
          console.log(`🔍 Using FMP ticker: ${ticker}`);
          
          try {
          data.fmp = await fmpService.getQuote(ticker);
            console.log('✅ FMP quote data loaded successfully:', data.fmp.symbol);
            
            // Also get historical data for better analysis
            try {
              const historicalData = await fmpService.getHistoricalData(ticker, '1day', 30);
              if (historicalData && historicalData.length > 0) {
                data.fmp.historicalData = historicalData;
                console.log(`📈 Historical data loaded: ${historicalData.length} data points`);
              }
            } catch (historicalError) {
              console.log('⚠️ Historical data not available for', ticker);
            }
          } catch (error) {
            console.error('❌ FMP API error:', error);
            // Try fallback to AAPL
            try {
              data.fmp = await fmpService.getQuote('AAPL');
              console.log('🔄 Using AAPL as FMP fallback');
            } catch (fallbackError) {
              console.error('❌ FMP fallback also failed:', fallbackError);
            }
          }
        }
      }
    } catch (error) {
      console.error('❌ Error gathering API data:', error);
    }
    
    console.log('📊 Final API data gathered:', Object.keys(data));
    return data;
  }

  private extractFREDIndicator(query: string, analysis: QueryAnalysis): string {
    const lowerQuery = query.toLowerCase();
    
    // Check if user explicitly mentioned an indicator
    if (analysis.entities.economicIndicators && analysis.entities.economicIndicators.length > 0) {
      return analysis.entities.economicIndicators[0];
    }
    
    // Pattern matching for common economic indicators
    if (lowerQuery.includes('gdp') || lowerQuery.includes('gross domestic product')) return 'gdp';
    if (lowerQuery.includes('unemployment') || lowerQuery.includes('jobless')) return 'unemployment';
    if (lowerQuery.includes('inflation') || lowerQuery.includes('cpi') || lowerQuery.includes('consumer price')) return 'inflation';
    if (lowerQuery.includes('interest rate') || lowerQuery.includes('fed funds') || lowerQuery.includes('federal funds')) return 'interest rate';
    if (lowerQuery.includes('employment') || lowerQuery.includes('jobs')) return 'employment';
    if (lowerQuery.includes('housing') || lowerQuery.includes('home')) return 'housing';
    if (lowerQuery.includes('retail') || lowerQuery.includes('sales')) return 'retail';
    if (lowerQuery.includes('industrial') || lowerQuery.includes('production')) return 'industrial';
    
    // Default to GDP for general economic queries
    return 'gdp';
  }

  private extractFMPTicker(query: string, analysis: QueryAnalysis): string {
    const lowerQuery = query.toLowerCase();
    
    // Check if user explicitly mentioned a ticker
    if (analysis.entities.tickers && analysis.entities.tickers.length > 0) {
      return analysis.entities.tickers[0];
    }
    
    // Pattern matching for common company names
    if (lowerQuery.includes('apple') || lowerQuery.includes('iphone') || lowerQuery.includes('mac')) return 'AAPL';
    if (lowerQuery.includes('google') || lowerQuery.includes('alphabet')) return 'GOOGL';
    if (lowerQuery.includes('microsoft') || lowerQuery.includes('windows') || lowerQuery.includes('office')) return 'MSFT';
    if (lowerQuery.includes('tesla') || lowerQuery.includes('electric car')) return 'TSLA';
    if (lowerQuery.includes('amazon') || lowerQuery.includes('ecommerce')) return 'AMZN';
    if (lowerQuery.includes('meta') || lowerQuery.includes('facebook')) return 'META';
    if (lowerQuery.includes('nvidia') || lowerQuery.includes('gpu')) return 'NVDA';
    if (lowerQuery.includes('netflix')) return 'NFLX';
    if (lowerQuery.includes('disney')) return 'DIS';
    if (lowerQuery.includes('coca cola') || lowerQuery.includes('coke')) return 'KO';
    if (lowerQuery.includes('mcdonalds')) return 'MCD';
    if (lowerQuery.includes('walmart')) return 'WMT';
    if (lowerQuery.includes('home depot')) return 'HD';
    if (lowerQuery.includes('jpmorgan') || lowerQuery.includes('jp morgan')) return 'JPM';
    if (lowerQuery.includes('bank of america')) return 'BAC';
    if (lowerQuery.includes('wells fargo')) return 'WFC';
    
    // Default to AAPL for general market queries
    return 'AAPL';
  }

  private mapIndicatorToFREDSeries(indicator: string): string {
    const mapping: { [key: string]: string } = {
      'gdp': 'GDP',
      'unemployment': 'UNRATE',
      'inflation': 'CPIAUCSL',
      'interest rate': 'FEDFUNDS',
      'fed funds': 'FEDFUNDS',
      'employment': 'PAYEMS',
      'housing': 'HOUST',
      'retail': 'RSAFS',
      'industrial': 'INDPRO',
      'economic': 'GDP',
      'economy': 'GDP'
    };
    
    return mapping[indicator.toLowerCase()] || 'GDP';
  }

  private async synthesizeResponse(
    query: string, 
    apiData: any, 
    conversationHistory: MoonshotMessage[],
    llmModel: 'moonshot' | 'gemini' = 'moonshot',
    selectedGeminiModel?: string
  ): Promise<{ content: string }> {
    console.log('🧠 LLM Synthesis Debug:', {
      llmModel,
      queryLength: query.length,
      apiDataKeys: Object.keys(apiData),
      conversationHistoryLength: conversationHistory.length,
      conversationContext: conversationHistory.slice(-3).map(msg => `${msg.role}: ${msg.content.substring(0, 50)}...`)
    });

    // Create clean data context without system instructions
    const dataContext = this.buildDataContext(query, apiData);
    
    // Create system instructions separately (not visible to user)
    const systemInstructions = this.buildSystemInstructions(conversationHistory, apiData);
    
    if (llmModel === 'gemini') {
      console.log('🤖 Using Gemini AI for synthesis');
      const geminiService = apiIntegrationService.getGeminiService();
      
      if (!geminiService) {
        console.error('❌ Gemini service not available');
        return this.createFallbackSynthesis(query, apiData);
      }
      
      // Prepare messages for Gemini with clean data context
      const geminiMessages = [
        // Recent conversation history (last 8 messages for better context)
        ...conversationHistory.slice(-8).map(msg => ({
          id: msg.id,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: msg.timestamp
        })),
        // Current query with clean data context (no system instructions visible)
        {
          id: `context-${Date.now()}`,
          role: 'user' as const,
          content: dataContext,
          timestamp: Date.now()
        }
      ];
      
      try {
        const modelToUse = selectedGeminiModel || 'gemini-2.0-flash';
        console.log(`📤 Sending request to Gemini API with model: ${modelToUse}`);
        const response = await geminiService.sendMessage(geminiMessages, modelToUse);
        console.log('✅ Gemini API response received');
        return {
          content: response.choices[0]?.message?.content || this.createFallbackSynthesis(query, apiData).content
        };
      } catch (error) {
        console.error('❌ Gemini synthesis error:', error);
        return this.createFallbackSynthesis(query, apiData);
      }
    } else {
      console.log('🤖 Using Moonshot AI for synthesis');
      // Use Moonshot (default)
    const moonshotService = apiIntegrationService.getMoonshotService();
    
    if (!moonshotService) {
        console.error('❌ Moonshot service not available');
      return this.createFallbackSynthesis(query, apiData);
    }
    
    const messages: MoonshotMessage[] = [
        // Recent conversation history (last 8 messages for better context)
        ...conversationHistory.slice(-8),
        // Current query with clean data context (no system instructions visible)
      {
        id: `context-${Date.now()}`,
        role: 'user',
          content: dataContext,
        timestamp: Date.now()
      }
    ];
    
    try {
      const response = await moonshotService.sendMessage(messages, 'moonshot-v1-32k');
      return {
        content: response.choices[0]?.message?.content || this.createFallbackSynthesis(query, apiData).content
      };
    } catch (error) {
        console.error('❌ Moonshot synthesis error:', error);
      return this.createFallbackSynthesis(query, apiData);
      }
    }
  }

  private buildSystemInstructions(conversationHistory: MoonshotMessage[], apiData: any): string {
    let instructions = `You are a data analyst assistant. You are having a conversation with a user about financial and economic data analysis.\n\n`;
    
    // Add conversation context
    if (conversationHistory.length > 0) {
      instructions += `CONVERSATION CONTEXT:\n`;
      instructions += `This is an ongoing conversation. Previous exchanges have covered:\n`;
      
      // Summarize recent conversation topics
      const recentMessages = conversationHistory.slice(-6);
      recentMessages.forEach((msg, idx) => {
        const role = msg.role === 'assistant' ? 'Assistant' : 'User';
        const content = msg.content.length > 100 ? msg.content.substring(0, 100) + '...' : msg.content;
        instructions += `- ${role}: ${content}\n`;
      });
      instructions += '\n';
    }
    
    // Add data context
    if (apiData.dataset) {
      instructions += `CURRENT DATA CONTEXT: You are analyzing the dataset "${apiData.dataset.name}" with ${apiData.dataset.totalRecords} records.\n`;
    } else if (apiData.fred) {
      instructions += `CURRENT DATA CONTEXT: You are analyzing FRED economic data for "${apiData.fred.title}".\n`;
    } else if (apiData.fmp) {
      instructions += `CURRENT DATA CONTEXT: You are analyzing FMP market data for ${apiData.fmp.symbol} (${apiData.fmp.name}).\n`;
    } else {
      instructions += `CURRENT DATA CONTEXT: No specific data source is currently selected.\n`;
    }
    
    instructions += `\nCORE INSTRUCTIONS:\n`;
    instructions += `1. You are a data analyst with expertise in financial and economic analysis\n`;
    instructions += `2. For DATA ANALYSIS: Use ONLY the specific data provided below as your primary data source\n`;
    instructions += `3. For INSIGHTS & EXPLANATIONS: Apply your general knowledge, creativity, and analytical expertise\n`;
    instructions += `4. For DEEP ANALYSIS: Use your understanding of economic principles, market dynamics, and financial concepts\n`;
    instructions += `5. For CONTEXT & INTERPRETATION: Provide broader context, explanations, and insights beyond just the raw data\n`;
    instructions += `6. Maintain conversation continuity and reference previous exchanges when relevant\n`;
    instructions += `7. Build upon previous insights and analysis\n`;
    instructions += `8. If the user asks follow-up questions, use the conversation history for context\n\n`;
    
    return instructions;
  }

  private buildDataContext(query: string, apiData: any): string {
    let context = `USER QUERY: "${query}"\n\n`;
    
    let hasData = false;
    
    if (apiData.dataset) {
      hasData = true;
      context += `DATASET TO ANALYZE:\n`;
      context += `- Name: ${apiData.dataset.name}\n`;
      context += `- Description: ${apiData.dataset.description}\n`;
      context += `- Total Records: ${apiData.dataset.totalRecords}\n`;
      context += `- Columns: ${apiData.dataset.columns.join(', ')}\n`;
      
      if (apiData.dataset.data && apiData.dataset.data.length > 0) {
        // For small datasets (≤ 100 rows), show all data
        if (apiData.dataset.data.length <= 100) {
          context += `- Complete Dataset (${apiData.dataset.data.length} rows):\n`;
          context += apiData.dataset.data.map((row: any, idx: number) => 
            `  Row ${idx + 1}: ${JSON.stringify(row)}`
          ).join('\n');
        } 
        // For medium datasets (101-1000 rows), show sample + summary stats
        else if (apiData.dataset.data.length <= 1000) {
          context += `- Data Sample (first 20 rows of ${apiData.dataset.data.length}):\n`;
          const sampleData = apiData.dataset.data.slice(0, 20);
          context += sampleData.map((row: any, idx: number) => 
            `  Row ${idx + 1}: ${JSON.stringify(row)}`
          ).join('\n');
          
          context += `\n- Statistical Summary:\n`;
          context += this.generateDatasetSummary(apiData.dataset.data, apiData.dataset.columns);
        }
        // For large datasets (>1000 rows), show sample + comprehensive summary
        else {
          context += `- Data Sample (first 50 rows of ${apiData.dataset.data.length}):\n`;
          const sampleData = apiData.dataset.data.slice(0, 50);
          context += sampleData.map((row: any, idx: number) => 
            `  Row ${idx + 1}: ${JSON.stringify(row)}`
          ).join('\n');
          
          context += `\n- Comprehensive Statistical Summary:\n`;
          context += this.generateDatasetSummary(apiData.dataset.data, apiData.dataset.columns);
          
          // Add random sample from middle and end
          context += `\n- Additional Random Sample (10 rows from throughout dataset):\n`;
          const randomIndices = this.getRandomIndices(apiData.dataset.data.length, 10);
          randomIndices.forEach((idx, sampleIdx) => {
            context += `  Row ${idx + 1}: ${JSON.stringify(apiData.dataset.data[idx])}\n`;
          });
        }
        context += '\n\n';
      }
    }
    
    if (apiData.fred) {
      hasData = true;
      context += `FRED ECONOMIC DATA TO ANALYZE:\n`;
      context += `- Series: ${apiData.fred.title}\n`;
      context += `- Units: ${apiData.fred.units}\n`;
      context += `- Frequency: ${apiData.fred.frequency}\n`;
      context += `- Data Points: ${apiData.fred.data?.length || 0}\n`;
      
      if (apiData.fred.data && apiData.fred.data.length > 0) {
        context += `- Recent Values:\n`;
        const recentData = apiData.fred.data.slice(-10);
        recentData.forEach((point: any, idx: number) => {
          context += `  ${point.date}: ${point.value} ${apiData.fred.units}\n`;
        });
        context += '\n';
      }
    }
    
    if (apiData.fmp) {
      hasData = true;
      context += `FMP MARKET DATA TO ANALYZE:\n`;
      context += `- Symbol: ${apiData.fmp.symbol}\n`;
      context += `- Company: ${apiData.fmp.name}\n`;
      context += `- Current Price: $${apiData.fmp.price}\n`;
      context += `- Change: ${apiData.fmp.changesPercentage}% (${apiData.fmp.change >= 0 ? '+' : ''}${apiData.fmp.change})\n`;
      context += `- Day Range: $${apiData.fmp.dayLow} - $${apiData.fmp.dayHigh}\n`;
      context += `- 52-Week Range: $${apiData.fmp.yearLow} - $${apiData.fmp.yearHigh}\n`;
      context += `- Market Cap: $${(apiData.fmp.marketCap / 1000000000).toFixed(2)}B\n`;
      context += `- Volume: ${apiData.fmp.volume?.toLocaleString() || 'N/A'}\n`;
      context += `- 50-Day Avg: $${apiData.fmp.priceAvg50}\n`;
      context += `- 200-Day Avg: $${apiData.fmp.priceAvg200}\n`;
      
      if (apiData.fmp.historicalData && apiData.fmp.historicalData.length > 0) {
        context += `- Historical Data (last 10 days):\n`;
        const recentHistory = apiData.fmp.historicalData.slice(-10);
        recentHistory.forEach((point: any) => {
          context += `  ${point.date}: $${point.value}\n`;
        });
      }
      context += '\n';
    }
    
    if (!hasData) {
      context += `NO DATA PROVIDED: The user has not selected any specific data source. You can still provide general insights and analysis using your knowledge, but for data-specific analysis, please ask them to select a data source (dataset, FRED economic data, or FMP market data).\n\n`;
    }
    
    context += `Please provide your analysis now. Use the data above as your primary source, but feel free to apply your expertise, provide context, and offer deeper insights:`;
    
    return context;
  }



  private createFallbackSynthesis(query: string, apiData: any): { content: string } {
    let response = `I've analyzed your query: "${query}"\n\n`;
    
    let hasData = false;
    
    if (apiData.dataset) {
      hasData = true;
      response += `📊 DATASET ANALYSIS:\n`;
      response += `• Dataset: ${apiData.dataset.name}\n`;
      response += `• Records: ${apiData.dataset.totalRecords.toLocaleString()}\n`;
      response += `• Columns: ${apiData.dataset.columns.join(', ')}\n`;
      
      if (apiData.dataset.data && apiData.dataset.data.length > 0) {
        response += `• Complete dataset contains ${apiData.dataset.totalRecords} records available for analysis\n`;
        response += `• Data structure suggests potential for ${apiData.dataset.columns.includes('date') || apiData.dataset.columns.includes('time') ? 'time-series analysis' : 'statistical analysis'}\n`;
        
        // Add statistical summary for larger datasets
        if (apiData.dataset.totalRecords > 100) {
          response += `• Dataset size: ${apiData.dataset.totalRecords > 1000 ? 'Large' : 'Medium'} (${apiData.dataset.totalRecords.toLocaleString()} rows)\n`;
          response += `• Statistical summary and representative samples provided for efficient analysis\n`;
        }
      }
      response += '\n';
    }
    
    if (apiData.fred) {
      hasData = true;
      response += `📊 FRED ECONOMIC DATA:\n`;
      response += `• Series: ${apiData.fred.title}\n`;
      response += `• Latest Value: ${apiData.fred.data?.[apiData.fred.data.length - 1]?.value || 'N/A'} ${apiData.fred.units}\n`;
      response += `• Data Points: ${apiData.fred.data?.length || 0}\n`;
      response += `• Frequency: ${apiData.fred.frequency}\n\n`;
    }
    
    if (apiData.fmp) {
      hasData = true;
      response += `📈 FMP MARKET DATA:\n`;
      response += `• Symbol: ${apiData.fmp.symbol} (${apiData.fmp.name})\n`;
      response += `• Current Price: $${apiData.fmp.price} (${apiData.fmp.changesPercentage >= 0 ? '+' : ''}${apiData.fmp.changesPercentage}%)\n`;
      response += `• Market Cap: $${(apiData.fmp.marketCap / 1000000000).toFixed(2)}B\n`;
      response += `• Volume: ${apiData.fmp.volume?.toLocaleString() || 'N/A'}\n`;
      response += `• 50-Day Avg: $${apiData.fmp.priceAvg50}\n`;
      response += `• 200-Day Avg: $${apiData.fmp.priceAvg200}\n\n`;
    }
    
    if (!hasData) {
      response += `💡 GENERAL ANALYSIS: While I don't have specific data selected, I can provide insights based on my knowledge of financial markets, economic principles, and market dynamics. Feel free to ask me about economic concepts, market trends, or financial analysis approaches.\n\n`;
    } else {
      response += `💡 COMPREHENSIVE ANALYSIS: Based on the data provided above, I can offer both data-driven insights and broader market context. I'll analyze `;
      if (apiData.dataset) response += `patterns in your dataset, `;
      if (apiData.fred) response += `trends in this economic indicator, `;
      if (apiData.fmp) response += `performance of this specific stock, `;
      response += `while also providing market context, economic insights, and strategic perspectives.`;
    }
    
    return { content: response };
  }

  private determineSource(analysis: QueryAnalysis): ChatAPIResponse['source'] {
    if (analysis.needsFRED && analysis.needsFMP) return 'combined';
    if (analysis.needsFRED) return 'fred';
    if (analysis.needsFMP) return 'fmp';
    if (analysis.needsGemini) return 'gemini';
    return 'moonshot';
  }

  private determineSourceFromPreferences(preferences?: UserPreferences): ChatAPIResponse['source'] | null {
    if (!preferences) return null;
    
    if (preferences.dataSource === 'fred') return 'fred';
    if (preferences.dataSource === 'fmp') return 'fmp';
    if (preferences.dataSource === 'dataset') {
      return preferences.llmModel; // Use the selected LLM for dataset analysis
    }
    
    return null;
  }

  private shouldGenerateChart(analysis: QueryAnalysis, apiData: any): boolean {
    return !!(apiData.fred?.data?.length > 0 || apiData.fmp);
  }

  private determineChartType(analysis: QueryAnalysis, apiData: any): ChatAPIResponse['chartType'] {
    if (apiData.fred?.data?.length > 5) return 'line';
    if (apiData.fmp) return 'bar';
    return 'table';
  }

  private createFallbackResponse(query: string): ChatAPIResponse {
    return {
      id: `fallback-${Date.now()}`,
      content: `I encountered an issue processing your query: "${query}". Please try rephrasing your question or check if the API services are available.`,
      source: 'moonshot',
      timestamp: Date.now(),
      hasChart: false,
      apiCalls: {
        moonshot: false,
        fred: false,
        fmp: false,
        gemini: false
      }
    };
  }

  async testAllAPIKeys(): Promise<{
    moonshot: boolean;
    fred: boolean;
    fmp: boolean;
    gemini: boolean;
  }> {
    console.log('🧪 Testing all API keys...');
    
    const results = {
      moonshot: false,
      fred: false,
      fmp: false,
      gemini: false
    };
    
    try {
      // Test Moonshot
      const moonshotService = apiIntegrationService.getMoonshotService();
      if (moonshotService) {
        try {
          const models = await moonshotService.getModels();
          results.moonshot = models.length > 0;
          console.log('✅ Moonshot API test:', results.moonshot, 'Models found:', models.length);
        } catch (error) {
          console.error('❌ Moonshot API test failed:', error);
        }
      }
      
      // Test FRED
      const fredService = apiIntegrationService.getFREDService();
      if (fredService) {
        try {
          const series = await fredService.searchSeries('GDP', 1);
          results.fred = series.length > 0;
          console.log('✅ FRED API test:', results.fred, 'Series found:', series.length);
        } catch (error) {
          console.error('❌ FRED API test failed:', error);
        }
      }
      
      // Test FMP
      const fmpService = apiIntegrationService.getFMPService();
      if (fmpService) {
        try {
          const quote = await fmpService.getQuote('AAPL');
          results.fmp = !!quote.symbol;
          console.log('✅ FMP API test:', results.fmp, 'Quote received for:', quote.symbol);
        } catch (error) {
          console.error('❌ FMP API test failed:', error);
        }
      }
      
      // Test Gemini
      const geminiService = apiIntegrationService.getGeminiService();
      if (geminiService) {
        try {
          const connectionTest = await geminiService.testConnection();
          results.gemini = connectionTest;
          console.log('✅ Gemini API test:', results.gemini);
        } catch (error) {
          console.error('❌ Gemini API test failed:', error);
        }
      }
      
    } catch (error) {
      console.error('❌ API key testing error:', error);
    }
    
    console.log('🧪 All API key test results:', results);
    return results;
  }

  private generateDatasetSummary(data: any[], columns: string[]): string {
    let summary = '';
    
    const numericColumns = columns.filter(col => {
      const sampleValues = data.slice(0, 100).map(row => row[col]);
      return sampleValues.some(val => typeof val === 'number' && !isNaN(val));
    });
    
    const textColumns = columns.filter(col => !numericColumns.includes(col));
    
    // Numeric column statistics
    if (numericColumns.length > 0) {
      summary += `  Numeric Columns (${numericColumns.length}):\n`;
      numericColumns.forEach(col => {
        const values = data.map(row => row[col]).filter(val => typeof val === 'number' && !isNaN(val));
        if (values.length > 0) {
          const min = Math.min(...values);
          const max = Math.max(...values);
          const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
          summary += `    ${col}: min=${min.toFixed(2)}, max=${max.toFixed(2)}, avg=${avg.toFixed(2)}, count=${values.length}\n`;
        }
      });
    }
    
    // Text column statistics
    if (textColumns.length > 0) {
      summary += `  Text/Categorical Columns (${textColumns.length}):\n`;
      textColumns.forEach(col => {
        const values = data.map(row => row[col]).filter(val => val != null && val !== '');
        const uniqueValues = [...new Set(values)];
        summary += `    ${col}: ${uniqueValues.length} unique values, ${values.length} non-empty entries`;
        if (uniqueValues.length <= 10) {
          summary += `, values: [${uniqueValues.slice(0, 5).join(', ')}${uniqueValues.length > 5 ? '...' : ''}]`;
        }
        summary += '\n';
      });
    }
    
    // Data treatment metrics
    summary += `  Data Treatment:\n`;
    summary += `    Total rows: ${data.length}\n`;
    summary += `    Complete rows: ${data.filter(row => columns.every(col => row[col] != null && row[col] !== '')).length}\n`;
    summary += `    Completion rate: ${((data.filter(row => columns.every(col => row[col] != null && row[col] !== '')).length / data.length) * 100).toFixed(1)}%\n`;
    
    return summary;
  }

  private getRandomIndices(totalLength: number, sampleSize: number): number[] {
    const indices: number[] = [];
    const step = Math.floor(totalLength / sampleSize);
    
    for (let i = 0; i < sampleSize; i++) {
      const randomOffset = Math.floor(Math.random() * step);
      const index = Math.min(i * step + randomOffset, totalLength - 1);
      indices.push(index);
    }
    
    return indices;
  }

  // Public method to check API availability
  async checkAPIAvailability(): Promise<{
    moonshot: boolean;
    fred: boolean;
    fmp: boolean;
    gemini: boolean;
  }> {
    return {
      moonshot: !!apiIntegrationService.getMoonshotService(),
      fred: !!apiIntegrationService.getFREDService(),
      fmp: !!apiIntegrationService.getFMPService(),
      gemini: !!apiIntegrationService.getGeminiService()
    };
  }
}

export const chatOrchestrator = new ChatOrchestrator(); 